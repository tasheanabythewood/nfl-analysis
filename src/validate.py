"""
Step 3. Validate the snapshot and the decision coding before any analysis.

This step describes the data. It makes no claim about coaching. Each check is
(id, title, why it matters, SQL); a failing check is logged with its error and
the rest still run.

Usage:
    python -m src.validate
"""

import datetime as dt
import textwrap

from . import config, db, definitions as d


CHECKS = [
    ("V01", "Rows per season",
     "Must match rows_written in the manifest. A gap means a file was truncated.",
     "SELECT season, COUNT(*) AS rows FROM raw_pbp GROUP BY 1 ORDER BY 1"),

    ("V02", "Grain: is (game_id, play_id) unique in both sources?",
     "The join assumes one row per play on each side. A duplicate key would "
     "copy a play's probabilities onto two rows.",
     """
     SELECT 'raw_pbp' AS source, COUNT(*) AS rows,
            COUNT(DISTINCT (game_id, play_id)) AS distinct_keys FROM raw_pbp
     UNION ALL
     SELECT 'raw_nfl4th', COUNT(*), COUNT(DISTINCT (game_id, play_id)) FROM raw_nfl4th
     """),

    ("V03", "Every row is a fourth down",
     "The ingest filter claims down == 4. Confirms it.",
     "SELECT down, COUNT(*) AS rows FROM raw_pbp GROUP BY 1"),

    ("V04", "How play types map to the NFL's own play-type field",
     "The decision rule reads both fields. This shows every combination it has "
     "to handle, including the penalty and aborted-snap edge cases.",
     """
     SELECT play_type, play_type_nfl, COUNT(*) AS rows
     FROM raw_pbp GROUP BY 1, 2 ORDER BY rows DESC
     """),

    ("V05", "Rows per series: how often a fourth down is replayed",
     "Series with more than one snapped fourth down are penalties or replays. "
     "Only the last snap is the decision; the rest must not be counted.",
     """
     SELECT snaps_in_series, COUNT(*) AS series
     FROM (SELECT game_id, series, COUNT(*) AS snaps_in_series
           FROM v WHERE is_snap GROUP BY 1, 2)
     GROUP BY 1 ORDER BY 1
     """),

    ("V06", "Decision coding on decision snaps",
     "The population the analysis uses. NULL means intent could not be "
     "established and the snap is excluded.",
     """
     SELECT coalesce(decision, '(excluded)') AS decision, COUNT(*) AS snaps,
            ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct
     FROM v WHERE is_decision_snap GROUP BY 1 ORDER BY snaps DESC
     """),

    ("V07", "Decision coding agrees with nflfastR's series result",
     "An independent check. series_result records how the set of downs ended. "
     "A coded punt should end in 'Punt'; a coded go should end in a first down, "
     "touchdown, turnover on downs or turnover. Disagreements are listed in V08.",
     """
     SELECT coalesce(decision, '(excluded)') AS decision, series_result, COUNT(*) AS snaps
     FROM v WHERE is_decision_snap
     GROUP BY 1, 2 ORDER BY 1, snaps DESC
     """),

    ("V08", "Examples: coded punt whose series did not end in a punt",
     "Fakes, blocked punts and penalties live here. Read them to confirm the "
     "coding reflects what the team chose, not what happened.",
     """
     SELECT game_id, play_id, series_result, left("desc", 140) AS description
     FROM v
     WHERE is_decision_snap AND decision = 'punt'
       AND coalesce(series_result, '') <> 'Punt'
     ORDER BY random() LIMIT 12
     """),

    ("V09", "Examples: excluded decision snaps",
     "Confirms nothing that is clearly a punt or an attempt is being dropped.",
     """
     SELECT play_type, play_type_nfl, series_result, left("desc", 120) AS description
     FROM v WHERE is_decision_snap AND decision IS NULL
     ORDER BY random() LIMIT 12
     """),

    ("V10", "Join coverage on decision snaps, by decision",
     "Every analysed snap needs nfl4th probabilities. Unmatched snaps are "
     "excluded; if they cluster in one decision type the result is biased.",
     """
     SELECT coalesce(decision, '(excluded)') AS decision, COUNT(*) AS snaps,
            SUM(CASE WHEN has_probs THEN 1 ELSE 0 END) AS with_probs,
            ROUND(100.0 * SUM(CASE WHEN has_probs THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct
     FROM v WHERE is_decision_snap GROUP BY 1 ORDER BY snaps DESC
     """),

    ("V11", "Examples: decision snaps without probabilities",
     "What the 1 to 2 percent of unmatched plays look like.",
     """
     SELECT game_id, play_id, decision, qtr, game_seconds_remaining,
            left("desc", 100) AS description
     FROM v WHERE is_decision_snap AND decision IS NOT NULL AND NOT has_probs
     ORDER BY random() LIMIT 10
     """),

    ("V12", "nfl4th rows that do not appear in play-by-play",
     "Orphans in the probability file for the analysed seasons. Should be zero "
     "or explained by the 2026 rows outside the window.",
     f"""
     SELECT CAST(left(n.game_id, 4) AS INT) AS season, COUNT(*) AS orphan_rows
     FROM raw_nfl4th n
     LEFT JOIN raw_pbp p USING (game_id, play_id)
     WHERE p.game_id IS NULL
     GROUP BY 1 ORDER BY 1
     """),

    ("V13", "Probability ranges and missingness on decision snaps",
     "Win probabilities must sit in [0, 1]. Missing punt_wp is expected deep in "
     "opponent territory, where nfl4th does not model a punt.",
     """
     SELECT COUNT(*) AS snaps,
            MIN(go_wp) AS min_go, MAX(go_wp) AS max_go,
            MIN(punt_wp) AS min_punt, MAX(punt_wp) AS max_punt,
            SUM(CASE WHEN go_wp IS NULL THEN 1 ELSE 0 END) AS null_go,
            SUM(CASE WHEN punt_wp IS NULL THEN 1 ELSE 0 END) AS null_punt,
            SUM(CASE WHEN fg_wp IS NULL THEN 1 ELSE 0 END) AS null_fg
     FROM v WHERE is_decision_snap AND has_probs
     """),

    ("V14", "Where punt_wp is missing, by field position",
     "If punt_wp is missing for any snap where teams actually punt, those punts "
     "silently fall out of the analysis.",
     """
     SELECT CAST(floor(yardline_100 / 10) * 10 AS INT) AS yards_from_goal_bucket,
            COUNT(*) AS snaps,
            SUM(CASE WHEN punt_wp IS NULL THEN 1 ELSE 0 END) AS null_punt_wp,
            SUM(CASE WHEN decision = 'punt' THEN 1 ELSE 0 END) AS punts,
            SUM(CASE WHEN decision = 'punt' AND punt_wp IS NULL THEN 1 ELSE 0 END)
                AS punts_with_null_punt_wp
     FROM v WHERE is_decision_snap AND has_probs
     GROUP BY 1 ORDER BY 1
     """),

    ("V15", "go_boost matches go_wp minus the best alternative",
     "Confirms the meaning of nfl4th's columns before redefining the measure. "
     "go_boost should equal 100 x (go_wp - max(punt_wp, fg_wp)).",
     """
     SELECT COUNT(*) AS snaps,
            MAX(ABS(go_boost - 100 * (go_wp - GREATEST(coalesce(punt_wp, 0),
                                                        coalesce(fg_wp, 0)))))
                AS max_abs_difference
     FROM v WHERE is_decision_snap AND has_probs AND go_boost IS NOT NULL
     """),

    ("V16", "Missing model inputs on decision snaps",
     "Every control named in the hypothesis must be present.",
     """
     SELECT COUNT(*) AS snaps,
            SUM(CASE WHEN ydstogo IS NULL THEN 1 ELSE 0 END) AS null_ydstogo,
            SUM(CASE WHEN yardline_100 IS NULL THEN 1 ELSE 0 END) AS null_yardline,
            SUM(CASE WHEN score_differential IS NULL THEN 1 ELSE 0 END) AS null_score,
            SUM(CASE WHEN game_seconds_remaining IS NULL THEN 1 ELSE 0 END) AS null_clock,
            SUM(CASE WHEN posteam_timeouts_remaining IS NULL THEN 1 ELSE 0 END) AS null_timeouts,
            SUM(CASE WHEN spread_line IS NULL THEN 1 ELSE 0 END) AS null_spread
     FROM v WHERE is_decision_snap AND decision IS NOT NULL
     """),

    ("V17", "Decisions by season",
     "Sanity check against what is publicly known: go rates rose sharply after "
     "2018. If they do not here, the coding is wrong.",
     """
     SELECT season, COUNT(*) AS decisions,
            ROUND(100.0 * AVG(CASE WHEN decision = 'go' THEN 1 ELSE 0 END), 1) AS pct_go,
            ROUND(100.0 * AVG(CASE WHEN decision = 'punt' THEN 1 ELSE 0 END), 1) AS pct_punt,
            ROUND(100.0 * AVG(CASE WHEN decision = 'field_goal' THEN 1 ELSE 0 END), 1) AS pct_fg
     FROM v WHERE is_decision_snap AND decision IS NOT NULL
     GROUP BY 1 ORDER BY 1
     """),

    ("V18", "Garbage-time share of punts",
     "How many punts the headline excludes under the 5 to 95 percent rule.",
     f"""
     SELECT COUNT(*) AS punts_with_probs,
            SUM(CASE WHEN {d.GARBAGE_TIME_SQL} THEN 1 ELSE 0 END) AS garbage_time,
            ROUND(100.0 * SUM(CASE WHEN {d.GARBAGE_TIME_SQL} THEN 1 ELSE 0 END)
                  / COUNT(*), 1) AS pct
     FROM v
     WHERE is_decision_snap AND decision = 'punt'
       AND go_wp IS NOT NULL AND punt_wp IS NOT NULL
     """),
]


def run_check(con, sql: str) -> str:
    try:
        df = con.execute(sql).df()
        return df.to_string(index=False) if len(df) else "(no rows)"
    except Exception as e:  # logged, not raised: one failure should not hide the rest
        return f"CHECK FAILED: {type(e).__name__}: {e}"


def main() -> None:
    con, manifest = db.connect()
    con.execute("SELECT setseed(0.42)")  # reproducible random examples
    db.create_working_view(con)

    snap = manifest["snapshot_date"]
    rows_written = {
        f["file"]: f["rows_written"] for f in manifest["files"] if "rows_written" in f
    }
    lines = [
        "# Validation log: NFL fourth-down decisions",
        "",
        f"- Snapshot date: {snap}",
        f"- Seasons: {manifest['seasons'][0]} to {manifest['seasons'][-1]}",
        f"- Fourth-down rows in manifest: {sum(rows_written.values()):,}",
        f"- Log generated: {dt.datetime.now().isoformat(timespec='seconds')}",
        "",
        "This log describes the data and the decision coding. It contains no "
        "findings about coaching. Interpretation begins in step 5.",
    ]
    for cid, title, why, sql in CHECKS:
        print(f"{cid}  {title}")
        lines += [
            "", f"## {cid}. {title}", "", f"*Why this matters:* {why}", "",
            "```sql", textwrap.dedent(sql).strip(), "```", "",
            "```", run_check(con, sql), "```",
        ]

    out = config.REPORTS_DIR / f"validation_log__{snap}.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
