# NFL fourth-down decisions

Do NFL teams punt in situations where going for it carries a higher modelled
win probability, and is it systematic or noise?

**The decision this project supports:** which fourth-down situations a coaching
staff should re-examine its default in, and how much win probability the
current default costs.

---

## Hypothesis

**Research question.** When NFL teams face fourth down, how often do they punt
despite having a higher modelled expected win probability by attempting the
conversion?

**H0.** After accounting for field position, yards to go, score, time remaining,
timeouts, and game strength, NFL teams do not systematically punt when going for
it offers greater expected win probability.

**H1.** NFL teams systematically punt in some fourth-down situations where going
for it offers greater expected win probability.

### How the hypothesis becomes testable

The controls listed in H0 are already *inputs* to the nfl4th win-probability
models (yardline, yards to go, score differential, seconds remaining, timeouts,
and the pre-game Vegas spread as the game-strength term). So "after accounting
for" is handled by comparing `go_wp` to `punt_wp` for the same snap.

"Systematic" is tested three ways. Rejecting H0 requires all three.

1. **Frequency beyond model noise.** Share of punts where
   `go_wp - punt_wp` exceeds a margin τ. Reported at τ = 0, 1, 2, 4 percentage
   points, so a reader can see the result does not hinge on small, uncertain
   edges. Game-clustered bootstrap confidence intervals.
2. **Structure.** If teams decided on win probability, then once the go
   advantage is known, nothing else about the situation should predict a punt.
   Logistic regression: `punted ~ go_advantage + situation features`, standard
   errors clustered by game. H0 predicts the situation coefficients are zero.
   Situation terms that stay significant mean the punt is driven by the
   situation itself (for example "own territory" or "4th and 2+"), not by the
   win probability.
3. **Persistence.** The pattern holds across seasons, not one bad year. Trend
   by season, 2014 onward.

---

## Data

| Source | What | Key |
| --- | --- | --- |
| nflverse `pbp` release, `play_by_play_{season}.parquet` | Every play, with game state | `game_id`, `play_id` |
| nfl4th `nfl4th_infrastructure` release, `pre_computed_go_boost.rds` | `go_wp`, `punt_wp`, `fg_wp`, `go_boost` per fourth down | `game_id`, `play_id` |

The `.rds` is the same file `nfl4th::load_4th_pbp(fast = TRUE)` joins, so the
probabilities match nfl4th exactly. It is read with `pyreadr`, which is why R is
not needed.

`go_boost` is go versus the **best alternative** (punt or field goal). This
project's question is go versus **punt**, so the core measure is
`go_wp - punt_wp`, computed here and defined in `src/definitions.py`.

---

## Environment

Windows. Anaconda, not venv. Always work from the project root.

```
conda activate nfl4th
cd C:\Users\tnbyt\projects\nflanalysis
python -m src.<module>
```

In Spyder: set the working directory to the project root and use
**Run > Run configuration > Run in console's namespace** with
`python -m src.<module>`, or run from the Anaconda Prompt. `python src\module.py`
fails because the modules use relative imports.

---

## Pipeline

| Step | Command | Does | Writes |
| --- | --- | --- | --- |
| 1 | (setup) | Environment, structure, plan | this file |
| 2 | `python -m src.ingest` | Snapshot both sources plus provenance manifests | `data/raw/` |
| 3 | `python -m src.validate` | Join coverage, decision coding, range checks | `reports/validation_log__*.md` |
| 4 | `python -m src.model` | Apply definitions, build the analysis table | `data/fourth.duckdb` |
| 5 | `python -m src.analysis` | The three tests above, sensitivity, cost | `reports/analysis_tables__*.md` |
| 6 | `python -m src.charts` | Figures plus alt text | `reports/charts/` |
| 7 | (writing) | Recommendation memo and README | `reports/recommendation_memo.md` |
| 8 | (site) | Case-study page and card on the portfolio | `../tasheanabythewood.github.io/` |

---

## Locked decisions

Confirmed 2026-10-04. Do not quietly revisit them; if one looks wrong, say so
and show the query.

1. **Seasons 2014 to 2025.** 2026 is in progress and stays out of the main
   result; it is the out-of-sample check once complete.
2. **Regular season and postseason both included**, with `season_type` kept.
3. **Decision coding follows nfl4th's own rule** (`load_4th_pbp`), extended to
   label punts and field goals, in `src/definitions.py`.
4. **Primary margin τ = 2 percentage points.** 0, 1 and 4 are sensitivity.
5. **Garbage time excluded from the headline:** either option's win probability
   below 5 or above 95 percent. That removes 18 percent of punts (V18).
6. **One decision per series.** The decision is the last snapped fourth down in
   nflfastR's `series`. 2,014 series contain a replayed fourth down (V05).
7. **The go-vs-punt population is snaps with a non-null `punt_wp`.** nfl4th does
   not model a punt inside roughly the opponent's 35; only 5 actual punts fall
   there (V14).

---

## What validation established (2026-10-04)

`reports/validation_log__2026-10-04.md` has the SQL and output for each.

- 50,095 fourth-down rows; `(game_id, play_id)` unique in both sources (V02).
- 47,892 decision snaps: 27,737 punts, 11,806 field goals, 8,286 go,
  63 excluded (V06). The 63 are hard-count offsides, intent unknown (V09).
- Coding agrees with nflfastR's `series_result`: 98.7 percent of coded punts end
  in "Punt"; the rest are return touchdowns, blocks and accepted penalties,
  which is still a punt decision (V07, V08).
- 98.7 percent of decision snaps have nfl4th probabilities. The unmatched are
  overtime and the final seconds of a half, which nfl4th does not compute (V11).
  **Overtime is therefore outside the analysis.**
- `go_boost` equals `100 × (go_wp − max(punt_wp, fg_wp))` exactly (V15), which
  confirms why this project computes go-vs-punt itself.
- No missing values in any control the hypothesis names (V16).
- Go rate rises from 12 percent (2014) to 24 percent (2025), matching the
  publicly known trend (V17).

---

## What the analysis found (2026-10-04)

`reports/analysis_tables__2026-10-04.md` has every table. Headline population:
25,318 go-or-punt decisions, 2014 to 2025, outside garbage time.

**H0 is rejected on all three tests.**

1. **Frequency and asymmetry.** 9.5 percent of punts (95% CI 9.1 to 9.9) came
   when going was better by more than 2 points. When going was better by 2+,
   teams punted 52.5 percent of the time; when punting was better by 2+, teams
   went for it 0.3 percent of the time. The errors are one-sided
   (difference 52.3 points, CI 50.6 to 53.9). It persists at a 4-point margin
   (31.4 vs 0.3 percent).
2. **Structure.** With the go advantage held fixed by a spline, field zone,
   distance, score and quarter still predict punting (joint Wald chi2 = 1,261,
   df 15, p < 1e-200). Field position dominates: at the same +3 point edge, the
   predicted punt rate is 92.6 percent at own 21-40 and 59.3 percent at
   opponent 49-35.
3. **Persistence.** The asymmetry is significant in all 12 seasons. It has
   halved: the punt rate when going was better by 2+ fell from 71 percent (2014)
   to 37 percent (2024 and 2025).

**Where:** 4th and 1 at own 21-40 is the largest single cost (485 punts, 16
expected wins forfeited across 12 seasons).
**Cost:** 72 expected wins forfeited at the 2-point margin, 0.19 per
team-season; 0.30 counting every positive edge.
**Teams:** 2023-2025 team punt rates range 23 to 64 percent, but the spread is
not distinguishable from chance (chi2 p = 0.061). **Do not rank or name teams.**
**Robustness:** 7.4 to 9.5 percent across variants; comparing go to the best of
punt and field goal gives 9.1 percent.

---

## Traps this project already hit

- **An unconstrained patsy `cr()` spline is collinear with the intercept.** Its
  basis sums to 1 in every row. The logit still converges with the same
  likelihood, but the clustered covariance is computed on a singular design, so
  Wald statistics changed with row order (809 to 980 for one term). Use
  `constraints='center'`; `src/analysis.py` now asserts the design is full rank.
- **Do not mix pip and conda for compiled libraries.** A pip scipy over conda's
  MKL crashed `scipy.linalg` (Windows 0xc06d007f). The environment is all
  conda-forge with OpenBLAS.
- **matplotlib's font DLL fails to load after duckdb and scipy in one process**
  on this machine. `src.run_all` runs each step in its own process.
- **`git add -A` picks up anything in the folder.** A personal notes file was
  committed and had to be scrubbed with a force-push. Check `git status`
  immediately before every commit.
- **Team-level rates look meaningful and are not** (chi2 p = 0.061). Do not rank
  teams.

---

## Known limits (state these on the site)

- **Model dependence.** Every finding is relative to nfl4th's models. The
  conversion model is trained on attempts teams chose to make, which are
  plausibly easier than the ones they declined.
- **Coaches know things the model does not:** injuries, weather beyond the basic
  fields, matchups, and what the next drive is likely to look like.
- **Win probability is not the only objective.** Job security and blame
  asymmetry are real incentives. This project measures the gap, not the motive.
- **The asymmetry has two readings.** Coaches may be too conservative, or they
  may correctly believe the conversion model is too optimistic for the attempts
  they decline (the selection point above). The data cannot separate the two;
  the persistence of a 4-point gap makes pure model error less plausible.
- **Opponent 34 and in is a selected population.** Field goals are excluded from
  the go-vs-punt comparison, so the remaining punts there are unusual. The
  standardised rate for that zone (7.1 percent) is not comparable to the others.

---

## Conventions

- `data/raw/` is immutable. Manifests are committed; data files are gitignored.
- The as-of date comes from the snapshot manifest, never today's date.
- `src/definitions.py` is the single source of truth for every metric.
- Rates are `SUM(numerator) / SUM(denominator)`. No average of a percentage.
- Notebooks explore, scripts produce.
- Charts follow the palette and alt-text rules from the cincy-311 project
  (`../cincy-311/reports/palette.md`) so the portfolio reads as one system.
