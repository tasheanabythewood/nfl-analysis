"""
Step 5. Test the hypothesis.

Reads data/fourth.duckdb (built by src.model). Writes:
  reports/analysis_tables__<snapshot>.md   every table, with the question it answers
  reports/exports/*.csv, metrics.json      inputs for the charts and the website

Three tests, all on the headline population (go or punt decision, both options
modelled, not garbage time). H0 is rejected only if all three point the same way.

  1. Frequency and asymmetry. How often teams punt when going is better by more
     than tau, and whether that error is more common than its mirror image
     (going when punting is better by more than tau). Random model noise
     produces symmetric errors; a systematic lean does not.
  2. Structure. Once the go advantage is known, do field position, distance,
     score or quarter still predict a punt? Under H0 they should not.
  3. Persistence. Does the lean hold in every season?

Confidence intervals resample whole games (cluster bootstrap), because plays in
the same game share a coach, weather and score state.

Usage:
    python -m src.analysis
"""

import json

import duckdb
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy.stats import chi2_contingency

from . import config, definitions as d

B = 2000          # bootstrap resamples
SEED = 20261004
EXPORTS = config.REPORTS_DIR / "exports"
EXPORTS.mkdir(exist_ok=True)

SITUATION_TERMS = ["field_zone", "distance_band", "score_state", "period"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def cluster_bootstrap(df: pd.DataFrame, cols: list[str], stat, seed=SEED) -> np.ndarray:
    """Resample games with replacement. `stat` maps per-game column sums to a value."""
    g = df.groupby("game_id")[cols].sum().to_numpy()
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(g), size=(B, len(g)))
    sums = g[idx].sum(axis=1)                       # B x len(cols)
    return np.array([stat(*row) for row in sums])


def ci(draws: np.ndarray) -> tuple[float, float]:
    lo, hi = np.nanpercentile(draws, [2.5, 97.5])
    return float(lo), float(hi)


def pct(x: float) -> str:
    return f"{100 * x:.1f}%"


class Report:
    def __init__(self, title: str):
        self.lines = [f"# {title}", ""]

    def section(self, heading: str, question: str, body, note: str | None = None):
        self.lines += ["", f"## {heading}", "", f"*Question:* {question}", ""]
        if isinstance(body, pd.DataFrame):
            self.lines += ["```", body.to_string(index=False), "```"]
        else:
            self.lines += [str(body)]
        if note:
            self.lines += ["", note]
        print(f"  {heading}")

    def write(self, path):
        path.write_text("\n".join(self.lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
def main() -> None:
    con = duckdb.connect(str(config.WAREHOUSE), read_only=True)
    snap = con.execute("SELECT snapshot_date FROM meta").fetchone()[0]
    all_rows = con.execute("SELECT * FROM decisions").df()
    con.close()

    pop_all = all_rows[all_rows.in_go_punt_population].copy()
    pop_all["punted"] = (pop_all.decision == "punt").astype(int)
    pop = pop_all[~pop_all.garbage_time].copy()          # headline population
    adv = pop.go_vs_punt_pp
    tau = d.TAU_PRIMARY
    metrics = {"snapshot_date": snap, "seasons": [config.FIRST_SEASON, config.LAST_SEASON],
               "tau_primary_pp": tau}

    rep = Report("Analysis tables: NFL fourth-down decisions")
    rep.lines += [f"- Snapshot: {snap}", f"- Seasons: {config.FIRST_SEASON} to {config.LAST_SEASON}",
                  f"- Headline margin tau: {tau} percentage points of win probability",
                  f"- Bootstrap: {B} game-level resamples, seed {SEED}"]

    # --- 0. Population reconciliation ---------------------------------------
    recon = pd.DataFrame([
        ("Decision snaps (validation V06)", len(all_rows)),
        ("  minus intent unknown", -(all_rows.exclusion_reason == "intent unknown").sum()),
        ("  minus no nfl4th probabilities", -(all_rows.exclusion_reason == "no nfl4th probabilities").sum()),
        ("  minus punt not modelled (opp 35 and in)", -(all_rows.exclusion_reason == "punt not modelled").sum()),
        ("  minus field goals in modelled territory",
         -((all_rows.exclusion_reason.isna()) & (all_rows.decision == "field_goal")).sum()),
        ("Go-vs-punt population", len(pop_all)),
        ("  minus garbage time", -pop_all.garbage_time.sum()),
        ("Headline population", len(pop)),
        ("    of which punts", int(pop.punted.sum())),
        ("    of which go", int((1 - pop.punted).sum())),
    ], columns=["step", "snaps"])
    assert recon.snaps.iloc[:5].sum() == len(pop_all), "reconciliation does not close"
    rep.section("0. Population", "Where does every decision snap go?", recon)
    metrics.update(headline_snaps=len(pop), headline_punts=int(pop.punted.sum()),
                   headline_go=int((1 - pop.punted).sum()))

    # --- 1a. Frequency -------------------------------------------------------
    punts = pop[pop.punted == 1].copy()
    rows = []
    for t in d.TAUS:
        punts["hit"] = (punts.go_vs_punt_pp > t).astype(int)
        punts["one"] = 1
        draws = cluster_bootstrap(punts, ["hit", "one"], lambda h, n: h / n)
        rate = punts.hit.mean()
        lo, hi = ci(draws)
        rows.append((t, int(punts.hit.sum()), len(punts), pct(rate), f"{pct(lo)} to {pct(hi)}"))
        if t == tau:
            metrics.update(should_go_punts=int(punts.hit.sum()), should_go_punt_share=rate,
                           should_go_punt_share_ci=[lo, hi])
    freq = pd.DataFrame(rows, columns=["tau_pp", "punts_go_better_by_tau", "punts", "share", "95% CI"])
    rep.section("1a. How often teams punt when going is better",
                "Of all headline punts, what share had a go win probability higher by more than tau?",
                freq,
                "Read the tau = 2 row as the headline. tau = 0 counts every edge, however small; "
                "tau = 4 keeps only large edges that model error is unlikely to explain.")

    # --- 1b. Asymmetry -------------------------------------------------------
    rows = []
    for t in d.TAUS:
        if t == 0:
            continue
        p = pop.assign(
            go_better=(adv > t).astype(int),
            punt_better=(adv < -t).astype(int),
        )
        p["punt_when_go_better"] = p.go_better * p.punted
        p["go_when_punt_better"] = p.punt_better * (1 - p.punted)
        cols = ["punt_when_go_better", "go_better", "go_when_punt_better", "punt_better"]
        draws = cluster_bootstrap(p, cols, lambda a, b, c, e: a / b - c / e)
        r1 = p.punt_when_go_better.sum() / p.go_better.sum()
        r2 = p.go_when_punt_better.sum() / p.punt_better.sum()
        lo, hi = ci(draws)
        rows.append((t, int(p.go_better.sum()), pct(r1), int(p.punt_better.sum()), pct(r2),
                     f"{100 * (r1 - r2):.1f} pts", f"{100 * lo:.1f} to {100 * hi:.1f}"))
        if t == tau:
            metrics.update(go_better_snaps=int(p.go_better.sum()),
                           punt_rate_when_go_better=r1,
                           punt_better_snaps=int(p.punt_better.sum()),
                           go_rate_when_punt_better=r2,
                           asymmetry_pts=100 * (r1 - r2), asymmetry_ci_pts=[100 * lo, 100 * hi])
    asym = pd.DataFrame(rows, columns=["tau_pp", "snaps_go_better", "punted_anyway",
                                       "snaps_punt_better", "went_anyway", "difference", "95% CI"])
    rep.section("1b. Are the errors one-sided?",
                "When one option is clearly better, how often do teams pick the other one, in each direction?",
                asym,
                "If coaches followed win probability and only made random mistakes, the two "
                "error rates would be similar. A large positive difference means the mistakes "
                "lean towards punting.")

    # Decision curve, for the chart
    bins = np.arange(-10, 11, 1)
    curve = (pop.assign(bin=pd.cut(adv.clip(-9.99, 9.99), bins, right=False))
                .groupby("bin", observed=True)
                .agg(snaps=("punted", "size"), punts=("punted", "sum")).reset_index())
    curve["left_pp"] = [b.left for b in curve["bin"]]
    curve["punt_rate"] = curve.punts / curve.snaps
    curve[["left_pp", "snaps", "punts", "punt_rate"]].to_csv(EXPORTS / "decision_curve.csv", index=False)
    rep.section("1c. Decision curve",
                "How does the punt rate change as going becomes more or less favourable? "
                "(Edges beyond +/-10 points are folded into the end bins.)",
                curve[["left_pp", "snaps", "punts", "punt_rate"]].round(3),
                "A team following win probability would punt almost always left of zero and "
                "almost never right of it.")

    # --- 2. Structure --------------------------------------------------------
    # constraints='center' is required: an unconstrained cr() basis sums to 1 in
    # every row, is collinear with the intercept, and makes the clustered
    # covariance (and every Wald test) depend on row order. Found 2026-10-05.
    formula = ("punted ~ cr(go_vs_punt_pp, df=5, constraints='center') + "
               + " + ".join(f"C({c})" for c in SITUATION_TERMS) + " + C(season)")
    fit = smf.logit(formula, data=pop).fit(
        disp=False, maxiter=200, cov_type="cluster", cov_kwds={"groups": pd.factorize(pop.game_id)[0]})
    exog = fit.model.exog
    assert np.linalg.matrix_rank(exog) == exog.shape[1], "structure model design is rank deficient"
    names = fit.params.index
    wald_rows = []
    for term in SITUATION_TERMS:
        idx = [n for n in names if n.startswith(f"C({term})")]
        R = np.zeros((len(idx), len(names)))
        for i, n in enumerate(idx):
            R[i, names.get_loc(n)] = 1
        w = fit.wald_test(R, scalar=True)
        wald_rows.append((term, len(idx), round(float(w.statistic), 1), f"{float(w.pvalue):.2g}"))
    idx_all = [n for n in names if any(n.startswith(f"C({t})") for t in SITUATION_TERMS)]
    R = np.zeros((len(idx_all), len(names)))
    for i, n in enumerate(idx_all):
        R[i, names.get_loc(n)] = 1
    w_all = fit.wald_test(R, scalar=True)
    wald_rows.append(("all four jointly", len(idx_all), round(float(w_all.statistic), 1),
                      f"{float(w_all.pvalue):.2g}"))
    wald = pd.DataFrame(wald_rows, columns=["situation term", "df", "Wald chi2", "p-value"])
    metrics.update(structure_joint_chi2=float(w_all.statistic), structure_joint_p=float(w_all.pvalue),
                   structure_n=int(fit.nobs), structure_pseudo_r2=float(fit.prsquared))
    rep.section("2a. Does the situation predict a punt beyond the win-probability edge?",
                "Logistic regression of punted on a flexible spline of the go advantage, the four "
                "situation bands and season, standard errors clustered by game. H0 predicts the "
                "situation terms are jointly zero.",
                wald,
                f"n = {int(fit.nobs):,}, pseudo R-squared = {fit.prsquared:.3f}.")

    # Standardised punt rates: every snap given the same +tau edge, situation varied.
    std_rows = []
    for term in ["field_zone", "distance_band", "score_state", "period"]:
        for level in sorted(pop[term].unique()):
            cf = pop.assign(go_vs_punt_pp=tau + 1.0, **{term: level})
            std_rows.append((term, level[2:], pct(fit.predict(cf).mean())))
    std = pd.DataFrame(std_rows, columns=["term", "level", f"predicted punt rate at +{tau + 1:g} pts"])
    std.to_csv(EXPORTS / "standardised_punt_rates.csv", index=False)
    rep.section("2b. Same edge, different situation",
                f"If every snap carried the same +{tau + 1:g} point edge for going, how would the "
                "punt rate differ by situation? (Model predictions averaged over the sample.)",
                std,
                "Under H0 each block would be flat. Differences are the situation itself "
                "driving the decision.")
    fz = std[std.term == "field_zone"].set_index("level").iloc[:, -1]
    metrics["standardised_punt_rate_by_field_zone"] = fz.to_dict()

    # --- 3. Persistence ------------------------------------------------------
    rows = []
    for season, s in pop.groupby("season"):
        s = s.assign(go_better=(s.go_vs_punt_pp > tau).astype(int),
                     punt_better=(s.go_vs_punt_pp < -tau).astype(int))
        s["a"] = s.go_better * s.punted
        s["c"] = s.punt_better * (1 - s.punted)
        draws = cluster_bootstrap(s, ["a", "go_better", "c", "punt_better"], lambda a, b, c, e: a / b - c / e)
        r1, r2 = s.a.sum() / s.go_better.sum(), s.c.sum() / s.punt_better.sum()
        lo, hi = ci(draws)
        r1_lo, r1_hi = ci(cluster_bootstrap(s, ["a", "go_better"], lambda a, b: a / b))
        sp = s[s.punted == 1]
        rows.append((season, int(s.go_better.sum()), r1, r1_lo, r1_hi, r2,
                     100 * (r1 - r2), 100 * lo, 100 * hi, (sp.go_vs_punt_pp > tau).mean()))
    trend = pd.DataFrame(rows, columns=["season", "snaps_go_better", "punt_rate_when_go_better",
                                        "punt_rate_ci_lo", "punt_rate_ci_hi",
                                        "go_rate_when_punt_better", "asymmetry_pts",
                                        "ci_lo_pts", "ci_hi_pts", "share_of_punts_go_better"])
    trend.to_csv(EXPORTS / "season_trend.csv", index=False)
    seasons_significant = int((trend.ci_lo_pts > 0).sum())
    metrics.update(seasons_with_significant_asymmetry=seasons_significant, seasons_total=len(trend),
                   punt_rate_when_go_better_first=float(trend.punt_rate_when_go_better.iloc[0]),
                   punt_rate_when_go_better_last=float(trend.punt_rate_when_go_better.iloc[-1]))
    rep.section("3. Does it hold every season?",
                f"Asymmetry at tau = {tau} by season, with game-clustered 95% CIs.",
                trend.round(3),
                f"Seasons where the CI excludes zero: {seasons_significant} of {len(trend)}.")

    # --- Where it happens ----------------------------------------------------
    gb = pop[pop.go_vs_punt_pp > tau]
    grid = (gb.groupby(["field_zone", "distance_band"])
              .agg(snaps_go_better=("punted", "size"), punted=("punted", "sum"),
                   wp_forfeited_pts=("go_vs_punt_pp", lambda x: x[gb.loc[x.index, "punted"] == 1].sum()))
              .reset_index())
    grid["punt_rate"] = grid.punted / grid.snaps_go_better
    grid["wp_forfeited_wins"] = grid.wp_forfeited_pts / 100
    grid.to_csv(EXPORTS / "situation_grid.csv", index=False)
    top = grid.sort_values("wp_forfeited_wins", ascending=False).head(10)
    rep.section("4. Where the costly punts are",
                f"Snaps where going was better by more than {tau} points, by field zone and distance. "
                "Sorted by expected wins forfeited through punting.",
                top.assign(field_zone=top.field_zone.str[2:], distance_band=top.distance_band.str[2:])
                   [["field_zone", "distance_band", "snaps_go_better", "punted", "punt_rate", "wp_forfeited_wins"]]
                   .round(3))

    # --- Cost ----------------------------------------------------------------
    team_seasons = pop_all.groupby(["season", "posteam"]).ngroups
    cost_rows = []
    for label, df in [("headline (no garbage time)", pop), ("all, incl. garbage time", pop_all)]:
        p = df[(df.punted == 1)]
        for t in [0.0, tau]:
            wins = p.loc[p.go_vs_punt_pp > t, "go_vs_punt_pp"].sum() / 100
            cost_rows.append((label, t, round(wins, 1), round(wins / team_seasons, 2)))
    cost = pd.DataFrame(cost_rows, columns=["population", "tau_pp", "expected_wins_forfeited",
                                            "per_team_season"])
    metrics.update(team_seasons=team_seasons,
                   wins_forfeited_headline_tau=float(cost.iloc[1].expected_wins_forfeited),
                   wins_forfeited_per_team_season_tau=float(cost.iloc[1].per_team_season),
                   wins_forfeited_all_tau0=float(cost.iloc[2].expected_wins_forfeited),
                   wins_forfeited_per_team_season_all_tau0=float(cost.iloc[2].per_team_season))
    rep.section("5. What it costs",
                "Sum of the win-probability edge given up on punts where going was better, "
                "expressed in expected wins.",
                cost,
                f"{team_seasons} team-seasons. These are model-expected wins, not observed ones.")

    # --- Team variation ------------------------------------------------------
    recent = pop[(pop.season >= 2023) & (pop.go_vs_punt_pp > tau)]
    teams = (recent.groupby("posteam").agg(snaps_go_better=("punted", "size"), punted=("punted", "sum"))
                   .reset_index())
    teams["punt_rate"] = teams.punted / teams.snaps_go_better
    teams = teams.sort_values("punt_rate")
    teams.to_csv(EXPORTS / "team_rates_2023_2025.csv", index=False)
    # Small samples per team: test whether the spread exceeds chance before
    # claiming teams differ. Chi-square test of homogeneity, 32 x 2 table.
    chi2, team_p, team_df, _ = chi2_contingency(
        np.column_stack([teams.punted, teams.snaps_go_better - teams.punted]))
    metrics.update(team_punt_rate_min=float(teams.punt_rate.min()),
                   team_punt_rate_max=float(teams.punt_rate.max()),
                   team_punt_rate_min_team=teams.posteam.iloc[0],
                   team_punt_rate_max_team=teams.posteam.iloc[-1],
                   team_homogeneity_chi2=float(chi2), team_homogeneity_p=float(team_p))
    rep.section("6. Team variation, 2023 to 2025",
                f"Among snaps where going was better by more than {tau} points, how often did each "
                "team punt anyway?",
                pd.concat([teams.head(5), teams.tail(5)]).round(3),
                "Lowest five and highest five shown; all 32 in reports/exports/team_rates_2023_2025.csv. "
                f"Chi-square test that all 32 teams share one punt rate: chi2 = {chi2:.1f}, "
                f"df = {team_df}, p = {team_p:.2g}. "
                + ("The spread between teams is larger than chance would produce."
                   if team_p < 0.05 else
                   "At 22 to 45 snaps per team, the spread is NOT distinguishable from chance. "
                   "Do not rank or name teams from this table; the pattern is league-wide."))

    # --- Robustness ----------------------------------------------------------
    rob = []
    def share(df):
        p = df[df.punted == 1]
        return pct((p.go_vs_punt_pp > tau).mean()), len(p)
    rob.append(("Headline", *share(pop)))
    rob.append(("Including garbage time", *share(pop_all)))
    rob.append(("Regular season only", *share(pop[pop.season_type == "REG"])))
    rob.append(("First half only (less score pressure)", *share(pop[pop.qtr <= 2])))
    p = pop[pop.punted == 1]
    rob.append(("Go better than BOTH punt and FG (go_boost)", pct((p.go_boost > tau).mean()), len(p)))
    rob = pd.DataFrame(rob, columns=["variant", f"share of punts with go better by > {tau} pts", "punts"])
    rep.section("7. Robustness",
                "Does the headline share survive reasonable changes to the population or the comparison?",
                rob)

    out = config.REPORTS_DIR / f"analysis_tables__{snap}.md"
    rep.write(out)
    (EXPORTS / "metrics.json").write_text(json.dumps(metrics, indent=2, default=float))
    print(f"\nWrote {out}\nWrote {EXPORTS / 'metrics.json'}")


if __name__ == "__main__":
    main()
