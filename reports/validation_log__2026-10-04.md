# Validation log: NFL fourth-down decisions

- Snapshot date: 2026-10-04
- Seasons: 2014 to 2025
- Fourth-down rows in manifest: 50,095
- Log generated: 2026-10-05T12:47:52

This log describes the data and the decision coding. It contains no findings about coaching. Interpretation begins in step 5.

## V01. Rows per season

*Why this matters:* Must match rows_written in the manifest. A gap means a file was truncated.

```sql
SELECT season, COUNT(*) AS rows FROM raw_pbp GROUP BY 1 ORDER BY 1
```

```
 season  rows
   2014  4117
   2015  4199
   2016  4082
   2017  4233
   2018  3977
   2019  4042
   2020  3832
   2021  4254
   2022  4300
   2023  4490
   2024  4279
   2025  4290
```

## V02. Grain: is (game_id, play_id) unique in both sources?

*Why this matters:* The join assumes one row per play on each side. A duplicate key would copy a play's probabilities onto two rows.

```sql
SELECT 'raw_pbp' AS source, COUNT(*) AS rows,
       COUNT(DISTINCT (game_id, play_id)) AS distinct_keys FROM raw_pbp
UNION ALL
SELECT 'raw_nfl4th', COUNT(*), COUNT(DISTINCT (game_id, play_id)) FROM raw_nfl4th
```

```
    source  rows  distinct_keys
   raw_pbp 50095          50095
raw_nfl4th 50121          50121
```

## V03. Every row is a fourth down

*Why this matters:* The ingest filter claims down == 4. Confirms it.

```sql
SELECT down, COUNT(*) AS rows FROM raw_pbp GROUP BY 1
```

```
 down  rows
  4.0 50095
```

## V04. How play types map to the NFL's own play-type field

*Why this matters:* The decision rule reads both fields. This shows every combination it has to handle, including the penalty and aborted-snap edge cases.

```sql
SELECT play_type, play_type_nfl, COUNT(*) AS rows
FROM raw_pbp GROUP BY 1, 2 ORDER BY rows DESC
```

```
 play_type                play_type_nfl  rows
      punt                         PUNT 27544
field_goal                   FIELD_GOAL 11690
      pass                         PASS  4346
       run                         RUSH  2737
   no_play                  UNSPECIFIED  1515
   no_play                      PENALTY  1188
      pass                         SACK   380
      pass                 INTERCEPTION   239
       run                  UNSPECIFIED   195
      pass                  UNSPECIFIED   128
       NaN                  UNSPECIFIED    83
  qb_kneel                         RUSH    37
      punt                  UNSPECIFIED    10
      pass FUMBLE_RECOVERED_BY_OPPONENT     3
```

## V05. Rows per series: how often a fourth down is replayed

*Why this matters:* Series with more than one snapped fourth down are penalties or replays. Only the last snap is the decision; the rest must not be counted.

```sql
SELECT snaps_in_series, COUNT(*) AS series
FROM (SELECT game_id, series, COUNT(*) AS snaps_in_series
      FROM v WHERE is_snap GROUP BY 1, 2)
GROUP BY 1 ORDER BY 1
```

```
 snaps_in_series  series
               1   45878
               2    1949
               3      61
               4       4
```

## V06. Decision coding on decision snaps

*Why this matters:* The population the analysis uses. NULL means intent could not be established and the snap is excluded.

```sql
SELECT coalesce(decision, '(excluded)') AS decision, COUNT(*) AS snaps,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct
FROM v WHERE is_decision_snap GROUP BY 1 ORDER BY snaps DESC
```

```
  decision  snaps   pct
      punt  27737 57.92
field_goal  11806 24.65
        go   8286 17.30
(excluded)     63  0.13
```

## V07. Decision coding agrees with nflfastR's series result

*Why this matters:* An independent check. series_result records how the set of downs ended. A coded punt should end in 'Punt'; a coded go should end in a first down, touchdown, turnover on downs or turnover. Disagreements are listed in V08.

```sql
SELECT coalesce(decision, '(excluded)') AS decision, series_result, COUNT(*) AS snaps
FROM v WHERE is_decision_snap
GROUP BY 1, 2 ORDER BY 1, snaps DESC
```

```
  decision     series_result  snaps
(excluded)        First down     61
(excluded) Turnover on downs      1
(excluded)       End of half      1
field_goal        Field goal   9982
field_goal Missed field goal   1687
field_goal        First down    113
field_goal          QB kneel     11
field_goal     Opp touchdown     11
field_goal       End of half      2
        go        First down   3783
        go Turnover on downs   3437
        go         Touchdown    710
        go          Turnover    307
        go     Opp touchdown     29
        go            Safety     12
        go          QB kneel      4
        go       End of half      3
        go              Punt      1
      punt              Punt  27372
      punt     Opp touchdown    156
      punt        First down    153
      punt            Safety     25
      punt Turnover on downs     18
      punt         Touchdown      8
      punt          Turnover      4
      punt          QB kneel      1
```

## V08. Examples: coded punt whose series did not end in a punt

*Why this matters:* Fakes, blocked punts and penalties live here. Read them to confirm the coding reflects what the team chose, not what happened.

```sql
SELECT game_id, play_id, series_result, left("desc", 140) AS description
FROM v
WHERE is_decision_snap AND decision = 'punt'
  AND coalesce(series_result, '') <> 'Punt'
ORDER BY random() LIMIT 12
```

```
        game_id  play_id     series_result                                                                                                                                  description
2015_10_BUF_NYJ   3540.0 Turnover on downs (5:17) (Punt formation) 6-C.Schmidt FUMBLES (Aborted) at BUF 13, and recovers at BUF 13. 6-C.Schmidt to BUF 13 for no gain (54-J.Lattimore).
2024_08_TEN_DET   2479.0     Opp touchdown                                      (13:05) 4-R.Stonehouse punts 56 yards to DET 10, Center-46-M.Cox. 11-K.Raymond for 90 yards, TOUCHDOWN.
2021_03_IND_TEN   2354.0        First down (4:56) 6-B.Kern punts 56 yards to IND 21, Center-46-M.Cox. 21-N.Hines to IND 32 for 11 yards (44-T.Carter). PENALTY on IND-44-Z.Franklin, Ro
2017_01_ARI_DET    590.0 Turnover on downs (6:21) (Punt formation) 2-K.Redfern FUMBLES (Aborted) at DET -8, and recovers at DET -8. 2-K.Redfern pushed ob at DET 13 for 21 yards (80-I.
  2023_03_NO_GB   1260.0     Opp touchdown                                       (10:47) 19-D.Whelan punts 40 yards to NO 24, Center-42-M.Orzech. 22-R.Shaheed for 76 yards, TOUCHDOWN.
2023_20_HOU_BAL   1570.0     Opp touchdown                                              (4:34) 11-J.Stout punts 45 yards to HOU 33, Center-69-T.Ott. 82-S.Sims for 67 yards, TOUCHDOWN.
2017_07_SEA_NYG    315.0        First down (10:45) 9-B.Wing punts 47 yards to SEA 29, Center-51-Z.DeOssie. 16-T.Lockett to SEA 29 for no gain (37-R.Cockrell). PENALTY on SEA-19-T.McEv
 2023_15_WAS_LA   1935.0 Turnover on downs (:39) (Punt formation) 5-T.Way Aborted. 54-C.Cheeseman FUMBLES at WAS 24, touched at WAS 17, recovered by WAS-5-T.Way at WAS 15. WAS-5-T.Way
2019_01_CIN_SEA    502.0        First down (7:51) 10-K.Huber punts 52 yards to SEA 5, Center-46-C.Harris, out of bounds. PENALTY on SEA-57-C.Barton, Running Into the Kicker, 5 yards, 
2016_02_ATL_OAK   2298.0        First down (13:52) 7-M.King punts 64 yards to end zone, Center-59-J.Condo, Touchback. Oakland challenged the too many players on field ruling, and the 
2015_06_WAS_NYJ   3856.0     Opp touchdown                      (4:04) 4-R.Quigley punt is BLOCKED by 20-J.Johnson, Center-46-T.Purdum, RECOVERED by WAS-19-R.Ross at NYJ 0. TOUCHDOWN.
 2024_14_BUF_LA   1107.0     Opp touchdown (12:38) 8-S.Martin punt is BLOCKED by 35-J.Hummel, Center-69-R.Ferguson, RECOVERED by LA-84-H.Long at BUF 22. 84-H.Long for 22 yards, TOUCHD
```

## V09. Examples: excluded decision snaps

*Why this matters:* Confirms nothing that is clearly a punt or an attempt is being dropped.

```sql
SELECT play_type, play_type_nfl, series_result, left("desc", 120) AS description
FROM v WHERE is_decision_snap AND decision IS NULL
ORDER BY random() LIMIT 12
```

```
play_type play_type_nfl series_result                                                                                                            description
  no_play       PENALTY    First down            (6:12) (Shotgun) PENALTY on SEA-90-Ja.Reed, Neutral Zone Infraction, 4 yards, enforced at SEA 46 - No Play.
  no_play       PENALTY    First down            (:41) (No Huddle) PENALTY on LV-96-D.Autry, Neutral Zone Infraction, 6 yards, enforced at LAC 49 - No Play.
  no_play       PENALTY    First down          (2:00) (Run formation) PENALTY on TB-50-V.Vea, Neutral Zone Infraction, 5 yards, enforced at TB 47 - No Play.
  no_play       PENALTY    First down (:08) (No Huddle, Shotgun) PENALTY on DAL-56-D.Fowler, Neutral Zone Infraction, 5 yards, enforced at DAL 10 - No Play.
  no_play       PENALTY    First down                (10:21) (No Huddle) PENALTY on JAX-99-S.Marks, Defensive Offside, 2 yards, enforced at JAX 4 - No Play.
  no_play       PENALTY    First down   (3:15) (Run formation) PENALTY on NYG-22-A.Phillips, Neutral Zone Infraction, 5 yards, enforced at PHI 36 - No Play.
  no_play       PENALTY    First down   (14:14) (Run formation) PENALTY on CLE-26-D.Kindred, Neutral Zone Infraction, 5 yards, enforced at CLE 40 - No Play.
  no_play       PENALTY    First down                   (10:41) (No Huddle) PENALTY on JAX-97-R.Miller, Encroachment, 5 yards, enforced at JAX 38 - No Play.
  no_play       PENALTY    First down       (5:43) (Run formation) PENALTY on MIN-22-H.Smith, Neutral Zone Infraction, 2 yards, enforced at MIN 6 - No Play.
  no_play       PENALTY    First down     (1:02) (Run formation) PENALTY on WAS-95-J.Newton, Neutral Zone Infraction, 5 yards, enforced at WAS 49 - No Play.
  no_play       PENALTY    First down             (1:18) (Shotgun) PENALTY on DEN-93-D.Jones, Neutral Zone Infraction, 5 yards, enforced at NO 35 - No Play.
  no_play       PENALTY    First down         (13:32) (Shotgun) PENALTY on BAL-53-K.Van Noy, Neutral Zone Infraction, 5 yards, enforced at BAL 49 - No Play.
```

## V10. Join coverage on decision snaps, by decision

*Why this matters:* Every analysed snap needs nfl4th probabilities. Unmatched snaps are excluded; if they cluster in one decision type the result is biased.

```sql
SELECT coalesce(decision, '(excluded)') AS decision, COUNT(*) AS snaps,
       SUM(CASE WHEN has_probs THEN 1 ELSE 0 END) AS with_probs,
       ROUND(100.0 * SUM(CASE WHEN has_probs THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct
FROM v WHERE is_decision_snap GROUP BY 1 ORDER BY snaps DESC
```

```
  decision  snaps  with_probs   pct
      punt  27737     27536.0 99.28
field_goal  11806     11609.0 98.33
        go   8286      8061.0 97.28
(excluded)     63        62.0 98.41
```

## V11. Examples: decision snaps without probabilities

*Why this matters:* What the 1 to 2 percent of unmatched plays look like.

```sql
SELECT game_id, play_id, decision, qtr, game_seconds_remaining,
       left("desc", 100) AS description
FROM v WHERE is_decision_snap AND decision IS NOT NULL AND NOT has_probs
ORDER BY random() LIMIT 10
```

```
        game_id  play_id   decision  qtr  game_seconds_remaining                                                                                          description
2025_11_CIN_PIT   4387.0         go  4.0                    10.0                (:10) (Shotgun) 16-J.Flacco pass incomplete short right to 5-T.Higgins (42-J.Pierre).
2017_04_JAX_NYJ   4781.0 field_goal  5.0                    32.0            (:32) 7-C.Catanzaro 41 yard field goal is GOOD, Center-42-T.Hennessy, Holder-4-L.Edwards.
 2022_12_TB_CLE   4366.0       punt  5.0                   174.0         (2:54) 5-J.Camarda punts 36 yards to CLE 29, Center-97-Z.Triner, downed by TB-79-P.O'Connor.
2022_10_MIN_BUF   4940.0 field_goal  5.0                   225.0               (3:45) 1-G.Joseph 33 yard field goal is GOOD, Center-42-A.DePaola, Holder-14-R.Wright.
 2020_08_NO_CHI   4604.0       punt  5.0                   419.0 (6:59) 6-T.Morstead punts 31 yards to CHI 19, Center-49-Z.Wood. 82-Dw.Harris to CHI 19 for no gain (
2019_13_PHI_MIA   4397.0       punt  4.0                    15.0        (:15) (Punt formation) 2-M.Haack punts 28 yards to PHI 31, Center-46-T.Pepper, out of bounds.
2015_08_IND_CAR   4855.0 field_goal  5.0                   327.0                  (5:27) 9-G.Gano 52 yard field goal is GOOD, Center-44-J.Jansen, Holder-8-B.Nortman.
 2021_05_GB_CIN   4092.0 field_goal  5.0                   120.0             (2:00) 2-M.Crosby 49 yard field goal is GOOD, Center-43-H.Bradley, Holder-7-C.Bojorquez.
 2018_01_SF_MIN   4096.0         go  4.0                     2.0                                             (:02) (Shotgun) 8-K.Cousins pass incomplete short right.
2014_09_WAS_MIN   4340.0       punt  4.0                    12.0       (:12) (Punt formation) 18-J.Locke punts 36 yards to end zone, Center-46-C.Loeffler, Touchback.
```

## V12. nfl4th rows that do not appear in play-by-play

*Why this matters:* Orphans in the probability file for the analysed seasons. Should be zero or explained by the 2026 rows outside the window.

```sql
SELECT CAST(left(n.game_id, 4) AS INT) AS season, COUNT(*) AS orphan_rows
FROM raw_nfl4th n
LEFT JOIN raw_pbp p USING (game_id, play_id)
WHERE p.game_id IS NULL
GROUP BY 1 ORDER BY 1
```

```
 season  orphan_rows
   2026          705
```

## V13. Probability ranges and missingness on decision snaps

*Why this matters:* Win probabilities must sit in [0, 1]. Missing punt_wp is expected deep in opponent territory, where nfl4th does not model a punt.

```sql
SELECT COUNT(*) AS snaps,
       MIN(go_wp) AS min_go, MAX(go_wp) AS max_go,
       MIN(punt_wp) AS min_punt, MAX(punt_wp) AS max_punt,
       SUM(CASE WHEN go_wp IS NULL THEN 1 ELSE 0 END) AS null_go,
       SUM(CASE WHEN punt_wp IS NULL THEN 1 ELSE 0 END) AS null_punt,
       SUM(CASE WHEN fg_wp IS NULL THEN 1 ELSE 0 END) AS null_fg
FROM v WHERE is_decision_snap AND has_probs
```

```
 snaps   min_go   max_go     min_punt  max_punt  null_go  null_punt  null_fg
 47268 0.000005 0.999971 4.590421e-07   0.99995      0.0    12313.0      0.0
```

## V14. Where punt_wp is missing, by field position

*Why this matters:* If punt_wp is missing for any snap where teams actually punt, those punts silently fall out of the analysis.

```sql
SELECT CAST(floor(yardline_100 / 10) * 10 AS INT) AS yards_from_goal_bucket,
       COUNT(*) AS snaps,
       SUM(CASE WHEN punt_wp IS NULL THEN 1 ELSE 0 END) AS null_punt_wp,
       SUM(CASE WHEN decision = 'punt' THEN 1 ELSE 0 END) AS punts,
       SUM(CASE WHEN decision = 'punt' AND punt_wp IS NULL THEN 1 ELSE 0 END)
           AS punts_with_null_punt_wp
FROM v WHERE is_decision_snap AND has_probs
GROUP BY 1 ORDER BY 1
```

```
 yards_from_goal_bucket  snaps  null_punt_wp  punts  punts_with_null_punt_wp
                      0   3387        3387.0    0.0                      0.0
                     10   4105        4105.0    0.0                      0.0
                     20   4282        4282.0    2.0                      2.0
                     30   4603         539.0  522.0                      3.0
                     40   5094           0.0 3537.0                      0.0
                     50   6135           0.0 5143.0                      0.0
                     60   7322           0.0 6558.0                      0.0
                     70   7259           0.0 6882.0                      0.0
                     80   3827           0.0 3670.0                      0.0
                     90   1254           0.0 1222.0                      0.0
```

## V15. go_boost matches go_wp minus the best alternative

*Why this matters:* Confirms the meaning of nfl4th's columns before redefining the measure. go_boost should equal 100 x (go_wp - max(punt_wp, fg_wp)).

```sql
SELECT COUNT(*) AS snaps,
       MAX(ABS(go_boost - 100 * (go_wp - GREATEST(coalesce(punt_wp, 0),
                                                   coalesce(fg_wp, 0)))))
           AS max_abs_difference
FROM v WHERE is_decision_snap AND has_probs AND go_boost IS NOT NULL
```

```
 snaps  max_abs_difference
 47268                 0.0
```

## V16. Missing model inputs on decision snaps

*Why this matters:* Every control named in the hypothesis must be present.

```sql
SELECT COUNT(*) AS snaps,
       SUM(CASE WHEN ydstogo IS NULL THEN 1 ELSE 0 END) AS null_ydstogo,
       SUM(CASE WHEN yardline_100 IS NULL THEN 1 ELSE 0 END) AS null_yardline,
       SUM(CASE WHEN score_differential IS NULL THEN 1 ELSE 0 END) AS null_score,
       SUM(CASE WHEN game_seconds_remaining IS NULL THEN 1 ELSE 0 END) AS null_clock,
       SUM(CASE WHEN posteam_timeouts_remaining IS NULL THEN 1 ELSE 0 END) AS null_timeouts,
       SUM(CASE WHEN spread_line IS NULL THEN 1 ELSE 0 END) AS null_spread
FROM v WHERE is_decision_snap AND decision IS NOT NULL
```

```
 snaps  null_ydstogo  null_yardline  null_score  null_clock  null_timeouts  null_spread
 47829           0.0            0.0         0.0         0.0            0.0          0.0
```

## V17. Decisions by season

*Why this matters:* Sanity check against what is publicly known: go rates rose sharply after 2018. If they do not here, the coding is wrong.

```sql
SELECT season, COUNT(*) AS decisions,
       ROUND(100.0 * AVG(CASE WHEN decision = 'go' THEN 1 ELSE 0 END), 1) AS pct_go,
       ROUND(100.0 * AVG(CASE WHEN decision = 'punt' THEN 1 ELSE 0 END), 1) AS pct_punt,
       ROUND(100.0 * AVG(CASE WHEN decision = 'field_goal' THEN 1 ELSE 0 END), 1) AS pct_fg
FROM v WHERE is_decision_snap AND decision IS NOT NULL
GROUP BY 1 ORDER BY 1
```

```
 season  decisions  pct_go  pct_punt  pct_fg
   2014       3941    12.2      63.5    24.3
   2015       4045    12.8      63.5    23.7
   2016       3936    13.0      62.2    24.8
   2017       4061    12.9      62.8    24.3
   2018       3819    15.2      61.1    23.6
   2019       3851    16.8      58.6    24.6
   2020       3643    19.6      55.0    25.4
   2021       4036    21.1      54.7    24.2
   2022       4110    19.1      56.2    24.7
   2023       4278    20.2      55.4    24.4
   2024       4049    20.8      52.6    26.5
   2025       4060    23.8      50.6    25.6
```

## V18. Garbage-time share of punts

*Why this matters:* How many punts the headline excludes under the 5 to 95 percent rule.

```sql
SELECT COUNT(*) AS punts_with_probs,
       SUM(CASE WHEN (LEAST(go_wp, punt_wp) < 0.05 OR GREATEST(go_wp, punt_wp) > 0.95) THEN 1 ELSE 0 END) AS garbage_time,
       ROUND(100.0 * SUM(CASE WHEN (LEAST(go_wp, punt_wp) < 0.05 OR GREATEST(go_wp, punt_wp) > 0.95) THEN 1 ELSE 0 END)
             / COUNT(*), 1) AS pct
FROM v
WHERE is_decision_snap AND decision = 'punt'
  AND go_wp IS NOT NULL AND punt_wp IS NOT NULL
```

```
 punts_with_probs  garbage_time  pct
            27531        4971.0 18.1
```
