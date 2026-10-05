"""
DuckDB connection with the raw snapshot exposed as two views.

  raw_pbp      fourth-down play-by-play, every season in the snapshot
  raw_nfl4th   nfl4th precomputed probabilities, as published

The snapshot is chosen from the newest manifest, and the as-of date comes from
that manifest, never from today's date.
"""

import json

import duckdb
import pyreadr

from . import config, definitions as d


def latest_manifest() -> dict:
    manifests = sorted(config.RAW_DIR.glob("snapshot__*.manifest.json"))
    if not manifests:
        raise FileNotFoundError("No snapshot manifest. Run python -m src.ingest first.")
    return json.loads(manifests[-1].read_text())


def connect(database: str = ":memory:") -> tuple[duckdb.DuckDBPyConnection, dict]:
    manifest = latest_manifest()
    files = [config.RAW_DIR / f["file"] for f in manifest["files"]]
    pbp = [f.as_posix() for f in files if f.name.startswith("pbp_")]
    rds = next(f for f in files if f.suffix == ".rds")

    con = duckdb.connect(database)
    con.execute(f"CREATE OR REPLACE VIEW raw_pbp AS SELECT * FROM read_parquet({pbp!r})")

    nfl4th = next(iter(pyreadr.read_r(rds).values()))
    nfl4th["play_id"] = nfl4th["play_id"].astype("float64")
    con.register("nfl4th_df", nfl4th)
    con.execute("CREATE OR REPLACE TABLE raw_nfl4th AS SELECT * FROM nfl4th_df")
    con.unregister("nfl4th_df")
    return con, manifest


# A working view: every fourth-down row, its coded decision, whether it is the
# decision snap for its series, and the nfl4th probabilities if they joined.
WORKING_VIEW = f"""
CREATE OR REPLACE VIEW v AS
WITH snaps AS (
    SELECT p.*,
           NOT ({d.NOT_A_SNAP_SQL}) AS is_snap
    FROM raw_pbp p
),
ranked AS (
    SELECT *,
           is_snap AND play_id = MAX(CASE WHEN is_snap THEN play_id END)
               OVER (PARTITION BY game_id, series) AS is_decision_snap,
           {d.DECISION_SQL} AS decision
    FROM snaps
)
SELECT r.*, n.go_wp, n.punt_wp, n.fg_wp, n.go_boost,
       n.game_id IS NOT NULL AS has_probs
FROM ranked r
LEFT JOIN raw_nfl4th n USING (game_id, play_id)
"""


def create_working_view(con) -> None:
    """View `v`: every fourth-down row, its decision, and nfl4th probabilities."""
    con.execute(WORKING_VIEW)
