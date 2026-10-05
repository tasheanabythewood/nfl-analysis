# Analysis tables: NFL fourth-down decisions

- Snapshot: 2026-10-04
- Seasons: 2014 to 2025
- Headline margin tau: 2.0 percentage points of win probability
- Bootstrap: 2000 game-level resamples, seed 20261004

## 0. Population

*Question:* Where does every decision snap go?

```
                                     step  snaps
          Decision snaps (validation V06)  47892
                     minus intent unknown    -63
            minus no nfl4th probabilities   -623
  minus punt not modelled (opp 35 and in) -12290
  minus field goals in modelled territory  -2268
                    Go-vs-punt population  32648
                       minus garbage time  -7330
                      Headline population  25318
                           of which punts  22560
                              of which go   2758
```

## 1a. How often teams punt when going is better

*Question:* Of all headline punts, what share had a go win probability higher by more than tau?

```
 tau_pp  punts_go_better_by_tau  punts share         95% CI
    0.0                    7374  22560 32.7% 32.1% to 33.4%
    1.0                    4176  22560 18.5% 18.0% to 19.0%
    2.0                    2146  22560  9.5%   9.1% to 9.9%
    4.0                     491  22560  2.2%   2.0% to 2.4%
```

Read the tau = 2 row as the headline. tau = 0 counts every edge, however small; tau = 4 keeps only large edges that model error is unlikely to explain.

## 1b. Are the errors one-sided?

*Question:* When one option is clearly better, how often do teams pick the other one, in each direction?

```
 tau_pp  snaps_go_better punted_anyway  snaps_punt_better went_anyway difference       95% CI
    1.0             6524         64.0%              11198        0.4%   63.6 pts 62.3 to 64.9
    2.0             4085         52.5%               7560        0.3%   52.3 pts 50.6 to 53.9
    4.0             1565         31.4%               2942        0.3%   31.0 pts 28.6 to 33.3
```

If coaches followed win probability and only made random mistakes, the two error rates would be similar. A large positive difference means the mistakes lean towards punting.

## 1c. Decision curve

*Question:* How does the punt rate change as going becomes more or less favourable? (Edges beyond +/-10 points are folded into the end bins.)

```
 left_pp  snaps  punts  punt_rate
     -10    138    137      0.993
      -9     96     96      1.000
      -8    205    205      1.000
      -7    423    420      0.993
      -6    751    750      0.999
      -5   1329   1324      0.996
      -4   1973   1968      0.997
      -3   2645   2639      0.998
      -2   3638   3613      0.993
      -1   4110   4034      0.982
       0   3486   3198      0.917
       1   2439   2030      0.832
       2   1602   1141      0.712
       3    918    514      0.560
       4    596    266      0.446
       5    360    112      0.311
       6    204     54      0.265
       7    112     25      0.223
       8     69     10      0.145
       9    224     24      0.107
```

A team following win probability would punt almost always left of zero and almost never right of it.

## 2a. Does the situation predict a punt beyond the win-probability edge?

*Question:* Logistic regression of punted on a flexible spline of the go advantage, the four situation bands and season, standard errors clustered by game. H0 predicts the situation terms are jointly zero.

```
  situation term  df  Wald chi2  p-value
      field_zone   4      985.1 6.2e-212
   distance_band   5      513.8 8.4e-109
     score_state   4      169.1  1.7e-35
          period   2       19.1  7.2e-05
all four jointly  15     1274.5 1.6e-262
```

n = 25,318, pseudo R-squared = 0.533.

## 2b. Same edge, different situation

*Question:* If every snap carried the same +3 point edge for going, how would the punt rate differ by situation? (Model predictions averaged over the sample.)

```
         term          level predicted punt rate at +3 pts
   field_zone       Own 1-20                         96.9%
   field_zone      Own 21-40                         92.9%
   field_zone      Own 41-50                         84.7%
   field_zone      Opp 49-35                         60.5%
   field_zone       Opp 34-1                          7.4%
distance_band         1 yard                         58.6%
distance_band        2 yards                         77.9%
distance_band        3 yards                         82.4%
distance_band      4-5 yards                         85.4%
distance_band      6-9 yards                         90.4%
distance_band      10+ yards                         89.6%
  score_state    Trailing 9+                         75.7%
  score_state   Trailing 1-8                         82.9%
  score_state           Tied                         87.4%
  score_state    Leading 1-8                         86.4%
  score_state     Leading 9+                         82.8%
       period     First half                         84.3%
       period  Third quarter                         85.8%
       period Fourth quarter                         82.1%
```

Under H0 each block would be flat. Differences are the situation itself driving the decision.

## 3. Does it hold every season?

*Question:* Asymmetry at tau = 2.0 by season, with game-clustered 95% CIs.

```
 season  snaps_go_better  punt_rate_when_go_better  go_rate_when_punt_better  asymmetry_pts  ci_lo_pts  ci_hi_pts  share_of_punts_go_better
   2014              342                     0.711                     0.006         70.406     65.604     74.914                     0.122
   2015              340                     0.688                     0.000         68.824     63.304     73.970                     0.111
   2016              327                     0.667                     0.005         66.191     60.192     71.864                     0.107
   2017              337                     0.685                     0.007         67.840     62.929     72.426                     0.112
   2018              316                     0.627                     0.002         62.497     57.021     68.285                     0.104
   2019              285                     0.477                     0.002         47.562     41.454     53.570                     0.076
   2020              306                     0.441                     0.000         44.118     38.518     49.523                     0.085
   2021              348                     0.434                     0.000         43.391     38.216     48.925                     0.085
   2022              401                     0.456                     0.003         45.344     40.166     50.826                     0.096
   2023              364                     0.420                     0.003         41.762     36.708     46.902                     0.078
   2024              343                     0.367                     0.003         36.421     30.606     41.895                     0.072
   2025              376                     0.367                     0.002         36.533     31.428     41.424                     0.082
```

Seasons where the CI excludes zero: 12 of 12.

## 4. Where the costly punts are

*Question:* Snaps where going was better by more than 2.0 points, by field zone and distance. Sorted by expected wins forfeited through punting.

```
field_zone distance_band  snaps_go_better  punted  punt_rate  wp_forfeited_wins
 Own 21-40        1 yard              668     485      0.726             16.086
 Own 41-50        1 yard              436     192      0.440              7.482
 Opp 49-35     4-5 yards              331     183      0.553              6.044
 Opp 49-35     6-9 yards              247     180      0.729              5.460
 Own 21-40       2 yards              173     158      0.913              5.109
 Own 41-50       2 yards              148     113      0.764              3.942
 Opp 49-35       3 yards              233     106      0.455              3.558
 Own 41-50     4-5 yards              135     109      0.807              3.274
 Opp 49-35       2 yards              273      85      0.311              3.120
  Own 1-20        1 yard               88      81      0.920              2.951
```

## 5. What it costs

*Question:* Sum of the win-probability edge given up on punts where going was better, expressed in expected wins.

```
                population  tau_pp  expected_wins_forfeited  per_team_season
headline (no garbage time)     0.0                    116.6             0.30
headline (no garbage time)     2.0                     72.4             0.19
   all, incl. garbage time     0.0                    123.9             0.32
   all, incl. garbage time     2.0                     73.1             0.19
```

384 team-seasons. These are model-expected wins, not observed ones.

## 6. Team variation, 2023 to 2025

*Question:* Among snaps where going was better by more than 2.0 points, how often did each team punt anyway?

```
posteam  snaps_go_better  punted  punt_rate
    PHI               39       9      0.231
    CAR               42      10      0.238
    DAL               29       7      0.241
    CHI               41      10      0.244
    NYG               34       9      0.265
    TEN               22      11      0.500
     LV               33      18      0.545
    LAC               45      25      0.556
    DEN               28      16      0.571
    HOU               22      14      0.636
```

Lowest five and highest five shown; all 32 in reports/exports/team_rates_2023_2025.csv. Chi-square test that all 32 teams share one punt rate: chi2 = 44.0, df = 31, p = 0.061. At 22 to 45 snaps per team, the spread is NOT distinguishable from chance. Do not rank or name teams from this table; the pattern is league-wide.

## 7. Robustness

*Question:* Does the headline share survive reasonable changes to the population or the comparison?

```
                                   variant share of punts with go better by > 2.0 pts  punts
                                  Headline                                       9.5%  22560
                    Including garbage time                                       7.9%  27531
                       Regular season only                                       9.5%  21604
     First half only (less score pressure)                                       7.4%  13917
Go better than BOTH punt and FG (go_boost)                                       9.1%  22560
```
