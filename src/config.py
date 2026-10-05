"""
Central configuration for the NFL fourth-down decision project.

Everything that could change between runs lives here. If a number or a name
appears in more than one script, it belongs in this file.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"            # immutable snapshots, never edited by hand
WAREHOUSE = DATA_DIR / "fourth.duckdb"  # built in step 4
REPORTS_DIR = PROJECT_ROOT / "reports"
CHARTS_DIR = REPORTS_DIR / "charts"

for _d in (RAW_DIR, REPORTS_DIR, CHARTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------
# Both are GitHub release assets. The release API gives each asset's size and
# last-updated timestamp, which go into the manifest as provenance.
GITHUB_API = "https://api.github.com/repos/{repo}/releases/tags/{tag}"

PBP_REPO, PBP_TAG = "nflverse/nflverse-data", "pbp"
PBP_ASSET = "play_by_play_{season}.parquet"

NFL4TH_REPO, NFL4TH_TAG = "nflverse/nfl4th", "nfl4th_infrastructure"
NFL4TH_ASSET = "pre_computed_go_boost.rds"

# ---------------------------------------------------------------------------
# Window
# ---------------------------------------------------------------------------
# nfl4th's precomputed probabilities start in 2014. 2026 is in progress and is
# excluded from the main result so the numbers do not move week to week.
FIRST_SEASON = 2014
LAST_SEASON = 2025
SEASONS = list(range(FIRST_SEASON, LAST_SEASON + 1))

# Columns kept from play-by-play. The full file has ~370 columns; these are the
# ones the definitions, validation and analysis use.
PBP_COLUMNS = [
    "game_id", "play_id", "season", "season_type", "week", "game_date",
    "fixed_drive", "series", "series_result",
    "posteam", "defteam", "home_team", "away_team",
    "down", "ydstogo", "yardline_100", "qtr", "game_seconds_remaining",
    "quarter_seconds_remaining", "score_differential",
    "posteam_timeouts_remaining", "defteam_timeouts_remaining",
    "spread_line", "vegas_wp", "wp",
    "play_type", "play_type_nfl", "rush", "pass", "aborted_play",
    "penalty", "desc", "first_down", "fourth_down_converted",
    "fourth_down_failed",
]
