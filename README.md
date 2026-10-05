# NFL fourth-down decisions

**When going for it is clearly better, NFL teams still punt about half the time.**

A hypothesis test on 47,892 fourth-down decisions, 2014 to 2025, using
nflverse play-by-play and the nfl4th win-probability models.

When going for it was better by 2 or more points of win probability, **teams
punted 52.5 percent of the time**. When punting was better by the same margin,
they went for it 0.3 percent of the time. Random mistakes would run both ways;
these run one way. The pattern holds in all 12 seasons. It has halved since 2014
(71 to 37 percent), but it has not closed.

**Recommendation:** on fourth and 1 or 2 from your own 21 to the opponent's 35,
make going for it the default when the edge is 2+ points. That band holds
53 percent of the win probability given up.

Read the [decision memo](reports/recommendation_memo.md) first.

---

## The hypothesis

**H0.** After accounting for field position, yards to go, score, time remaining,
timeouts and game strength, NFL teams do not systematically punt when going for
it offers greater expected win probability.

**H1.** Teams systematically punt in some situations where going for it offers
greater expected win probability.

Rejecting H0 required three independent tests to agree. All three did:

| Test | Question | Result |
| --- | --- | --- |
| Asymmetry | Are wrong punts more common than wrong attempts? | 52.5% vs 0.3%, difference CI 50.6 to 53.9 points |
| Structure | With the edge held fixed, does the situation still predict a punt? | Yes. Joint Wald chi-square 1,261, p < 1e-200 |
| Persistence | Does it hold every season? | Significant in 12 of 12 |

## What is here

| File | What it is |
| --- | --- |
| [`reports/recommendation_memo.md`](reports/recommendation_memo.md) | The decision, the evidence, the measurement plan, the limits |
| [`reports/analysis_tables__2026-10-04.md`](reports/analysis_tables__2026-10-04.md) | Every analysis table, with the question it answers |
| [`reports/validation_log__2026-10-04.md`](reports/validation_log__2026-10-04.md) | 18 checks on the data and the decision coding, with SQL and output |
| [`reports/charts/`](reports/charts/) | Five figures, with alt text |
| [`reports/exports/`](reports/exports/) | Small CSV and JSON summaries behind the charts |
| [`src/definitions.py`](src/definitions.py) | Every definition, in one place |
| [`CLAUDE.md`](CLAUDE.md) | Locked decisions, known traps, conventions |

## Four things that only showed up because the work was checked

**nfl4th's headline number answers a different question.** Its `go_boost`
compares going for it with the better of punting and kicking. Validation
confirmed it equals `go_wp - max(punt_wp, fg_wp)` to machine precision. This
project's question is go versus punt, so it computes its own measure.

**Fourth downs get counted twice.** After a delay of game or false start the
down is replayed, and both snaps appear in the data. 2,014 series contain a
replayed fourth down. Only the last snap counts as the decision.

**The obvious decision rule dropped real punts.** Coding intent from the
"Punt formation" text missed 195 punts and kicks with an accepted
post-snap penalty, whose description reads "punts 46 yards ... PENALTY". The
fix was found by reading the excluded rows, not by trusting the count.

**A regression gave a different answer every time the rows were shuffled.** An
unconstrained spline basis was collinear with the intercept. The model still
converged to the same likelihood, so nothing failed; only the Wald statistics
moved, between 809 and 980. The spline is now centred, the analysis asserts a
full-rank design, and two consecutive runs produce identical output.

And one finding that was deliberately left out: team-level punt rates for 2023
to 2025 range from 23 to 64 percent, which looks like a ranking. A significance
test says the spread is consistent with chance (p = 0.061), so no team is named.

## How it is built

Python, DuckDB, statsmodels. No R install needed: nfl4th's precomputed
probabilities are read from its published `.rds` file with `pyreadr`.

```
python -m src.run_all              # the whole pipeline, including a fresh download
python -m src.run_all --no-ingest  # reuse the existing snapshot
python -m src.run_all --from model # resume from a step
```

| Step | Command | Writes |
| --- | --- | --- |
| Snapshot both sources plus a provenance manifest | `python -m src.ingest` | `data/raw/` |
| 18 checks on grain, join coverage and decision coding | `python -m src.validate` | `reports/validation_log__*.md` |
| One row per decision snap, 8 build tests | `python -m src.model` | `data/fourth.duckdb` |
| The three tests, cost, robustness | `python -m src.analysis` | `reports/analysis_tables__*.md`, `reports/exports/` |
| Five figures plus alt text | `python -m src.charts` | `reports/charts/` |

### Design rules

1. **`data/raw/` is immutable.** Each pull writes a manifest with the source URL,
   the release's last-updated time, row counts and a SHA-256 hash. Manifests are
   committed; data files are gitignored and rebuilt from them.
2. **Definitions live in one file.** `src/definitions.py` holds the decision
   coding, the go-versus-punt measure, the margin and the situation bands.
3. **Flags, not filters.** Excluded snaps stay in the model with a reason, and
   the analysis reconciles every population back to the validation count.
4. **Uncertainty respects the data's structure.** Plays in one game share a
   coach, weather and score, so confidence intervals resample whole games and
   regression errors are clustered by game.
5. **Small edges are not headlined.** Results are reported at margins of 0, 1,
   2 and 4 points; the headline uses 2, outside plausible model error.

## Setup

Windows with Anaconda:

```
conda env create -f environment.yml
conda activate nfl4th
python -m src.run_all
```

Everything installs from conda-forge. Mixing in pip-installed compiled
libraries crashed `scipy.linalg` on Windows during this project.

## Sources and limits

- Play-by-play: [nflverse-data](https://github.com/nflverse/nflverse-data),
  `pbp` release, seasons 2014 to 2025.
- Win probabilities: [nfl4th](https://www.nfl4th.com),
  `pre_computed_go_boost.rds` from the `nfl4th_infrastructure` release, the same
  file `nfl4th::load_4th_pbp(fast = TRUE)` uses.
- Snapshot taken 4 October 2026.

Main limits, in full in the [memo](reports/recommendation_memo.md#limitations):

- **Model dependence.** Every finding is relative to nfl4th's models.
- **Two readings of the asymmetry.** Coaches may be too conservative, or the
  conversion model may be optimistic for the attempts they decline, since it is
  trained on attempts they chose to make. The data cannot separate the two.
- **Overtime and the opponent's 34-and-in are outside the comparison.**
- **Observational. No causal claims.**

Analysis and views are my own and are not affiliated with or endorsed by the
NFL, any club, or the nflverse project.
