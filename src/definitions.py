"""
Single source of truth for every definition in the project.

Validation, the model and the analysis all import from here. Change a
definition here, nowhere else, and rerun from validate.
"""

# ---------------------------------------------------------------------------
# Which rows are decision snaps
# ---------------------------------------------------------------------------
# A fourth down can appear several times: a delay of game or false start
# replays the down, and timeouts get their own row. The decision is the LAST
# snapped fourth-down play in the series (nflfastR's `series`). Earlier rows in
# the same series were superseded and would double-count the decision.
#
# Kneels and spikes are clock management, not a go/punt/kick choice.
NOT_A_SNAP_SQL = "play_type IS NULL OR play_type IN ('qb_kneel', 'qb_spike')"

# ---------------------------------------------------------------------------
# What the team chose
# ---------------------------------------------------------------------------
# Follows nfl4th::load_4th_pbp, extended to label punts and field goals
# explicitly (nfl4th only codes go vs not-go):
#   - aborted snap in punt formation       -> punt
#   - run or pass, not in punt/FG formation -> go   (includes fakes)
#   - run/pass/shotgun formation plus false start or neutral zone
#     infraction                           -> unknown intent, excluded
# Penalised snaps (play_type = 'no_play') take their intent from the formation
# or the play named in the description, because the play itself did not count.
# Without the "punts" / "yard field goal" wording, 195 punts and kicks with an
# accepted post-snap penalty were dropped (validation V09, 2026-10-04).
DECISION_SQL = r"""
CASE
    WHEN regexp_matches("desc", '(Run formation)|(Pass formation)|(Shotgun)')
     AND regexp_matches("desc", '(False Start)|(Neutral Zone Infraction)')
        THEN NULL
    WHEN aborted_play = 1 AND "desc" LIKE '%Punt formation%'
        THEN 'punt'
    WHEN (rush = 1 OR pass = 1)
     AND coalesce(play_type_nfl, '') NOT IN ('PUNT', 'FIELD_GOAL')
        THEN 'go'
    WHEN play_type = 'punt' OR play_type_nfl = 'PUNT'
        THEN 'punt'
    WHEN play_type = 'field_goal' OR play_type_nfl = 'FIELD_GOAL'
        THEN 'field_goal'
    WHEN play_type = 'no_play'
     AND regexp_matches("desc", '(Punt formation)|( punts )|(punt is BLOCKED)')
        THEN 'punt'
    WHEN play_type = 'no_play'
     AND regexp_matches("desc", '(Field Goal formation)|(yard field goal)')
        THEN 'field_goal'
    WHEN play_type = 'no_play'
     AND regexp_matches("desc", '(Run formation)|(Pass formation)|(Shotgun)')
        THEN 'go'
    ELSE NULL
END
"""

# ---------------------------------------------------------------------------
# The core measure
# ---------------------------------------------------------------------------
# Go versus PUNT, in percentage points of win probability. Not nfl4th's
# go_boost, which compares going to the best of punt and field goal.
GO_VS_PUNT_SQL = "100.0 * (go_wp - punt_wp)"

# Margins (percentage points) at which a punt counts as "going was better".
# TAU_PRIMARY is the headline; the rest are sensitivity.
TAUS = [0.0, 1.0, 2.0, 4.0]
TAU_PRIMARY = 2.0

# Garbage time: excluded from the headline when either option's win
# probability is outside these bounds. Decisions there barely move the result.
WP_FLOOR, WP_CEILING = 0.05, 0.95
GARBAGE_TIME_SQL = (
    f"(LEAST(go_wp, punt_wp) < {WP_FLOOR} OR GREATEST(go_wp, punt_wp) > {WP_CEILING})"
)

# ---------------------------------------------------------------------------
# Situation bands used by the structure test and the tables
# ---------------------------------------------------------------------------
# yardline_100 is yards from the opponent's goal line: 80 = own 20.
FIELD_ZONE_SQL = """
CASE
    WHEN yardline_100 > 80 THEN '1 Own 1-20'
    WHEN yardline_100 > 60 THEN '2 Own 21-40'
    WHEN yardline_100 >= 50 THEN '3 Own 41-50'
    WHEN yardline_100 >= 35 THEN '4 Opp 49-35'
    ELSE '5 Opp 34-1'
END
"""

DISTANCE_BAND_SQL = """
CASE
    WHEN ydstogo <= 1 THEN '1 1 yard'
    WHEN ydstogo = 2 THEN '2 2 yards'
    WHEN ydstogo = 3 THEN '3 3 yards'
    WHEN ydstogo <= 5 THEN '4 4-5 yards'
    WHEN ydstogo <= 9 THEN '5 6-9 yards'
    ELSE '6 10+ yards'
END
"""

SCORE_STATE_SQL = """
CASE
    WHEN score_differential <= -9 THEN '1 Trailing 9+'
    WHEN score_differential < 0 THEN '2 Trailing 1-8'
    WHEN score_differential = 0 THEN '3 Tied'
    WHEN score_differential <= 8 THEN '4 Leading 1-8'
    ELSE '5 Leading 9+'
END
"""

PERIOD_SQL = """
CASE
    WHEN qtr <= 2 THEN '1 First half'
    WHEN qtr = 3 THEN '2 Third quarter'
    ELSE '3 Fourth quarter'
END
"""
