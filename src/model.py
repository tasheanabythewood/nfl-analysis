"""
Step 4. Build the analysis table and test it.

Writes data/fourth.duckdb with one table:

  decisions   one row per fourth-down decision snap, 2014-2025, with the
              decision, nfl4th probabilities, the go-vs-punt measure and the
              situation bands. Every definition comes from src/definitions.py.

Flags rather than filters: excluded snaps stay in the table with the reason, so
every population in the analysis reconciles back to the validation counts.

Usage:
    python -m src.model
"""

from . import config, db, definitions as d

BUILD = f"""
CREATE OR REPLACE TABLE decisions AS
SELECT
    game_id, play_id, season, season_type, week, game_date,
    posteam, defteam, home_team, away_team,
    qtr, game_seconds_remaining, ydstogo, yardline_100, score_differential,
    posteam_timeouts_remaining, defteam_timeouts_remaining, spread_line,
    decision, series_result, "desc",
    go_wp, punt_wp, fg_wp, go_boost,
    {d.GO_VS_PUNT_SQL}                           AS go_vs_punt_pp,
    {d.GARBAGE_TIME_SQL}                         AS garbage_time,
    {d.FIELD_ZONE_SQL}                           AS field_zone,
    {d.DISTANCE_BAND_SQL}                        AS distance_band,
    {d.SCORE_STATE_SQL}                          AS score_state,
    {d.PERIOD_SQL}                               AS period,
    CASE
        WHEN decision IS NULL      THEN 'intent unknown'
        WHEN NOT has_probs         THEN 'no nfl4th probabilities'
        WHEN punt_wp IS NULL       THEN 'punt not modelled'
        ELSE NULL
    END                                          AS exclusion_reason,
    -- The go-vs-punt population: a go or punt decision, both options modelled.
    decision IN ('go', 'punt') AND punt_wp IS NOT NULL AND go_wp IS NOT NULL
                                                 AS in_go_punt_population
FROM v
WHERE is_decision_snap
"""

# (name, SQL returning one boolean, what a failure means)
TESTS = [
    ("decision snaps reconcile to validation V06",
     "SELECT COUNT(*) = 47892 FROM decisions",
     "the snap logic changed; rerun validate and update this number deliberately"),
    ("grain: one row per (game_id, play_id)",
     "SELECT COUNT(*) = COUNT(DISTINCT (game_id, play_id)) FROM decisions",
     "the build duplicated plays"),
    ("one decision per series",
     """SELECT COUNT(*) = 0 FROM (
            SELECT d.game_id, p.series FROM decisions d
            JOIN raw_pbp p USING (game_id, play_id)
            GROUP BY 1, 2 HAVING COUNT(*) > 1)""",
     "a replayed fourth down is being counted twice"),
    ("seasons are exactly the configured window",
     f"SELECT MIN(season) = {config.FIRST_SEASON} AND MAX(season) = {config.LAST_SEASON} FROM decisions",
     "the snapshot does not match config"),
    ("go_vs_punt_pp is go_wp minus punt_wp in points",
     """SELECT MAX(ABS(go_vs_punt_pp - 100 * (go_wp - punt_wp))) < 1e-9
        FROM decisions WHERE in_go_punt_population""",
     "the measure is not what definitions.py says"),
    ("every population row has a reason-free record",
     "SELECT COUNT(*) = 0 FROM decisions WHERE in_go_punt_population AND exclusion_reason IS NOT NULL",
     "a flagged row leaked into the analysis population"),
    ("no punt is lost from the population except where punts are not modelled",
     """SELECT COUNT(*) = 0 FROM decisions
        WHERE decision = 'punt' AND NOT in_go_punt_population
          AND exclusion_reason NOT IN ('no nfl4th probabilities', 'punt not modelled')""",
     "punts are being dropped for an undocumented reason"),
    ("every band is assigned",
     """SELECT COUNT(*) = 0 FROM decisions
        WHERE field_zone IS NULL OR distance_band IS NULL
           OR score_state IS NULL OR period IS NULL""",
     "a band CASE has a gap"),
]


def main() -> None:
    if config.WAREHOUSE.exists():
        config.WAREHOUSE.unlink()  # rebuilt from raw every time
    con, manifest = db.connect(str(config.WAREHOUSE))
    db.create_working_view(con)
    con.execute(BUILD)
    con.execute(f"CREATE OR REPLACE TABLE meta AS SELECT '{manifest['snapshot_date']}' AS snapshot_date")

    failed = 0
    for name, sql, meaning in TESTS:
        ok = bool(con.execute(sql).fetchone()[0])
        failed += not ok
        print(f"  {'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"  ->  {meaning}"))

    summary = con.execute("""
        SELECT coalesce(exclusion_reason, 'analysed') AS status,
               decision, COUNT(*) AS snaps
        FROM decisions GROUP BY ALL ORDER BY 1, 2
    """).df()
    print("\n" + summary.to_string(index=False))

    # Keep the warehouse self-contained: drop the views that point at raw files.
    con.execute("DROP VIEW v")
    con.execute("DROP VIEW raw_pbp")
    con.execute("DROP TABLE raw_nfl4th")
    con.close()

    if failed:
        raise SystemExit(f"\n{failed} test(s) failed. Fix before running the analysis.")
    print(f"\nAll {len(TESTS)} tests pass. Wrote {config.WAREHOUSE}")


if __name__ == "__main__":
    main()
