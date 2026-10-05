"""
Step 6. Static charts for the website, plus alt text.

Reads the CSVs and metrics.json written by src.analysis; recomputes nothing.
Writes PNG (for the site) and SVG (for print) to reports/charts/, and
alt_text.json / alt_text.md.

Palette and rules are the portfolio's, measured in
../cincy-311/reports/palette.md:
  - forest is the series the chart is about; mid grey is the comparison
  - sage is a fill only, never text or a thin line
  - alert sits only beside sage or white, never beside forest, grey or black
  - every series is direct-labelled, so colour never carries meaning alone
  - chart titles state the finding, not the variable

Usage:
    python -m src.charts
"""

import json

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.ticker import FuncFormatter, MultipleLocator

from . import config

EXPORTS = config.REPORTS_DIR / "exports"

ALERT = "#8c2f1f"
INK = "#000000"
FOREST = "#1a5442"
MIDGREY = "#737373"
SAGE = "#bed4c8"
GRID = "#d9d9d9"
BAND = "#eaeaea"
PAPER = "#ffffff"
RAMP_4 = ["#bed4c8", "#9fb6aa", "#759083", "#1a5442"]

plt.rcParams.update({
    "figure.facecolor": PAPER, "axes.facecolor": PAPER,
    "font.family": ["Arial", "Liberation Sans", "DejaVu Sans"],
    "font.size": 11, "text.color": INK, "axes.labelcolor": INK,
    "axes.edgecolor": GRID, "axes.linewidth": 1.0,
    "axes.grid": True, "axes.axisbelow": True,
    "grid.color": GRID, "grid.linewidth": 0.8,
    "xtick.color": MIDGREY, "ytick.color": MIDGREY,
    "xtick.labelcolor": MIDGREY, "ytick.labelcolor": MIDGREY,
    "axes.spines.top": False, "axes.spines.right": False,
    "svg.fonttype": "none",
})

PCT = FuncFormatter(lambda v, _: f"{v:.0%}")
SOURCE = "Source: nflverse play-by-play; nfl4th win-probability models. 2014–2025, garbage time excluded."
ALT: dict[str, str] = {}


def frame(title: str, subtitle: str, size=(9, 5.4)):
    fig, ax = plt.subplots(figsize=size)
    fig.subplots_adjust(left=0.09, right=0.96, top=0.80, bottom=0.16)
    fig.text(0.09, 0.94, title, fontsize=15, fontweight="bold", color=INK, va="top")
    fig.text(0.09, 0.875, subtitle, fontsize=10.5, color=MIDGREY, va="top", wrap=True)
    fig.text(0.09, 0.03, SOURCE, fontsize=8.5, color=MIDGREY)
    return fig, ax


def save(fig, name: str, alt: str):
    for ext in ("png", "svg"):
        fig.savefig(config.CHARTS_DIR / f"{name}.{ext}", dpi=200)
    plt.close(fig)
    ALT[name] = alt
    print(f"  {name}")


# ---------------------------------------------------------------------------
def decision_curve(m):
    c = pd.read_csv(EXPORTS / "decision_curve.csv")
    c["mid"] = c.left_pp + 0.5
    fig, ax = frame(
        "Teams keep punting well after going for it becomes the better call",
        "Share of go-or-punt decisions that were punts, by how much going for it changed win probability")
    ax.axvspan(0, 10, color=BAND, zorder=0, lw=0)
    ax.text(0.3, 0.06, "Going for it is better  →", color=INK, fontsize=10)
    ax.text(-0.3, 0.06, "←  Punting is better", color=INK, fontsize=10, ha="right")
    ax.plot(c.mid, c.punt_rate, color=FOREST, lw=2, marker="o", ms=6,
            mec=PAPER, mew=1.5, zorder=3)
    r = c.loc[c.left_pp == 3].iloc[0]
    ax.annotate(f"+3 to +4 points better to go:\nteams still punted {r.punt_rate:.0%}",
                xy=(r.mid, r.punt_rate), xytext=(5.2, 0.78), fontsize=10, color=INK,
                arrowprops=dict(arrowstyle="-", color=INK, lw=0.8))
    ax.set_xlim(-10, 10)
    ax.set_ylim(0, 1.04)
    ax.yaxis.set_major_formatter(PCT)
    ax.xaxis.set_major_locator(MultipleLocator(2))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:+.0f}" if v else "0"))
    ax.set_xlabel("Win probability of going for it minus punting (percentage points)", color=MIDGREY)
    ax.set_ylabel("Punted", color=MIDGREY)
    ax.grid(axis="x", visible=False)
    save(fig, "01-decision-curve",
         "Line chart of punt rate against the win-probability edge for going for it. Left of zero, "
         "where punting is better, teams punt nearly 100 percent of the time. Right of zero the line "
         f"falls slowly: at a 3 to 4 point edge for going, teams still punted {r.punt_rate:.0%}, and the "
         "punt rate does not drop below half until the edge passes about 4 points. A team following "
         "win probability would drop to near zero just right of zero.")


def asymmetry(m):
    t = m["tau_primary_pp"]
    vals = [m["go_rate_when_punt_better"], m["punt_rate_when_go_better"]]
    labels = [f"Punting was better by {t:g}+ points,\nteam went for it anyway",
              f"Going for it was better by {t:g}+ points,\nteam punted anyway"]
    ns = [m["punt_better_snaps"], m["go_better_snaps"]]
    fig, ax = frame("The mistakes run one way: toward the punt",
                    "How often teams chose the option with lower win probability, by direction of the mistake",
                    size=(9, 4.2))
    fig.subplots_adjust(left=0.36, top=0.74, bottom=0.2)
    ax.barh([0, 1], vals, color=[MIDGREY, FOREST], height=0.5)
    for y, v, n in zip([0, 1], vals, ns):
        ax.text(v + 0.012, y, f"{v:.1%}", va="center", fontsize=12, fontweight="bold", color=INK)
    ax.set_yticks([0, 1], [f"{l}\n({n:,} decisions)" for l, n in zip(labels, ns)],
                  color=INK, fontsize=10.5)
    ax.tick_params(axis="y", length=0)
    ax.set_xlim(0, 0.7)
    ax.xaxis.set_major_formatter(PCT)
    ax.grid(axis="y", visible=False)
    save(fig, "02-asymmetry",
         f"Two horizontal bars. When going for it was better by {t:g} or more points of win probability, "
         f"teams punted anyway {vals[1]:.1%} of the time across {ns[1]:,} decisions. When punting was "
         f"better by the same margin, teams went for it anyway {vals[0]:.1%} of the time across "
         f"{ns[0]:,} decisions. Random mistakes would be roughly balanced; these all lean toward punting.")


def season_trend(m):
    s = pd.read_csv(EXPORTS / "season_trend.csv")
    fig, ax = frame("The punting habit has halved since 2014, but it has not gone away",
                    f"Share of decisions where going for it was better by {m['tau_primary_pp']:g}+ points "
                    "and the team punted anyway, with 95% confidence interval")
    ax.fill_between(s.season, s.punt_rate_ci_lo, s.punt_rate_ci_hi, color=SAGE, lw=0, zorder=1)
    ax.plot(s.season, s.punt_rate_when_go_better, color=FOREST, lw=2, marker="o", ms=6,
            mec=PAPER, mew=1.5, zorder=3)
    ax.plot(s.season, s.go_rate_when_punt_better, color=MIDGREY, lw=2, marker="o", ms=5,
            mec=PAPER, mew=1.5, zorder=3)
    first, last = s.iloc[0], s.iloc[-1]
    ax.text(first.season, first.punt_rate_when_go_better + 0.06,
            f"{first.punt_rate_when_go_better:.0%}", ha="center", fontsize=11, fontweight="bold")
    ax.text(last.season, last.punt_rate_when_go_better + 0.06,
            f"{last.punt_rate_when_go_better:.0%}", ha="center", fontsize=11, fontweight="bold")
    ax.text(2019.5, 0.6, "Punted when going was better", color=INK, fontsize=10)
    ax.text(2019.5, 0.045, "Went for it when punting was better", color=INK, fontsize=10)
    ax.set_ylim(0, 0.85)
    ax.set_xlim(2013.5, 2025.5)
    ax.yaxis.set_major_formatter(PCT)
    ax.xaxis.set_major_locator(MultipleLocator(1))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"’{int(v) % 100:02d}"))
    ax.grid(axis="x", visible=False)
    save(fig, "03-season-trend",
         f"Line chart by season, 2014 to 2025. The share of clearly-go situations where teams punted "
         f"fell from {first.punt_rate_when_go_better:.0%} in 2014 to {last.punt_rate_when_go_better:.0%} "
         "in 2025, with most of the drop between 2018 and 2020. A second line, for going for it when "
         "punting was better, stays below 1 percent every season. The gap between the lines is "
         f"statistically significant in all {m['seasons_total']} seasons.")


def field_zone(m):
    s = pd.read_csv(EXPORTS / "standardised_punt_rates.csv")
    s = s[(s.term == "field_zone") & (s.level != "Opp 34-1")].copy()
    s["rate"] = s.iloc[:, 2].str.rstrip("%").astype(float) / 100
    s = s.iloc[::-1]  # own goal line at the top
    labels = {"Own 1-20": "Own 1 to 20", "Own 21-40": "Own 21 to 40",
              "Own 41-50": "Own 41 to midfield", "Opp 49-35": "Opponent 49 to 35"}
    fig, ax = frame("Same edge for going for it, different answer depending on field position",
                    "Predicted punt rate if every decision carried the same +3 point win-probability edge "
                    "for going for it",
                    size=(9, 4.6))
    fig.subplots_adjust(left=0.24, top=0.76, bottom=0.18)
    y = range(len(s))
    # Ordinal ramp follows field position: darkest at the team's own goal line.
    ax.barh(list(y), s.rate, color=RAMP_4, height=0.6)
    for yi, v in zip(y, s.rate):
        ax.text(v + 0.012, yi, f"{v:.0%}", va="center", fontsize=12, fontweight="bold", color=INK)
    ax.set_yticks(list(y), [labels[l] for l in s.level], color=INK)
    ax.tick_params(axis="y", length=0)
    ax.set_xlim(0, 1.08)
    ax.xaxis.set_major_formatter(PCT)
    ax.grid(axis="y", visible=False)
    rates = dict(zip(s.level, s.rate))
    save(fig, "04-field-position",
         "Four horizontal bars, ordered from a team's own goal line to the opponent's 35. Holding the "
         "win-probability edge for going for it fixed at +3 points, the model's predicted punt rate is "
         f"{rates['Own 1-20']:.0%} at a team's own 1 to 20, {rates['Own 21-40']:.0%} at its own 21 to 40, "
         f"{rates['Own 41-50']:.0%} from its own 41 to midfield, and {rates['Opp 49-35']:.0%} at the "
         "opponent's 49 to 35. If win probability drove the decision, all four bars would be equal.")


def costliest(m):
    g = pd.read_csv(EXPORTS / "situation_grid.csv")
    g = g.sort_values("wp_forfeited_wins", ascending=False).head(6).iloc[::-1]
    zone = {"1 Own 1-20": "own 1–20", "2 Own 21-40": "own 21–40", "3 Own 41-50": "own 41–50",
            "4 Opp 49-35": "opp 49–35", "5 Opp 34-1": "opp 34–1"}
    dist = {"1 1 yard": "4th & 1", "2 2 yards": "4th & 2", "3 3 yards": "4th & 3",
            "4 4-5 yards": "4th & 4–5", "5 6-9 yards": "4th & 6–9", "6 10+ yards": "4th & 10+"}
    labels = [f"{dist[d]}, {zone[z]}" for z, d in zip(g.field_zone, g.distance_band)]
    fig, ax = frame("Fourth and 1 in your own territory is where punting costs the most",
                    f"Expected wins given up by punting when going for it was better by "
                    f"{m['tau_primary_pp']:g}+ points, all teams, 2014–2025",
                    size=(9, 4.8))
    fig.subplots_adjust(left=0.24, top=0.76, bottom=0.17)
    colors = [SAGE] * (len(g) - 1) + [ALERT]
    ax.barh(range(len(g)), g.wp_forfeited_wins, color=colors, height=0.6)
    for yi, (w, n) in enumerate(zip(g.wp_forfeited_wins, g.punted)):
        ax.text(w + 0.2, yi, f"{w:.1f} wins", va="center", fontsize=11, fontweight="bold", color=INK)
        ax.text(w + 0.2, yi - 0.32, f"{int(n)} punts", va="center", fontsize=8.5, color=MIDGREY)
    ax.set_yticks(range(len(g)), labels, color=INK)
    ax.tick_params(axis="y", length=0)
    ax.set_xlim(0, g.wp_forfeited_wins.max() * 1.25)
    ax.set_xlabel("Expected wins forfeited", color=MIDGREY)
    ax.grid(axis="y", visible=False)
    top = g.iloc[-1]
    save(fig, "05-costliest-situations",
         f"Six horizontal bars ranking situations by expected wins forfeited through punting when going "
         f"for it was better by {m['tau_primary_pp']:g} or more points. Fourth and 1 between a team's own "
         f"21 and 40 is highlighted and largest, at {top.wp_forfeited_wins:.1f} expected wins from "
         f"{int(top.punted)} punts, more than twice the next situation. "
         + "; ".join(f"{l}: {w:.1f} wins" for l, w in zip(labels[-2::-1], g.wp_forfeited_wins.iloc[-2::-1]))
         + f". League-wide total at this margin: {m['wins_forfeited_headline_tau']:.0f} expected wins.")


def main():
    m = json.loads((EXPORTS / "metrics.json").read_text())
    decision_curve(m)
    asymmetry(m)
    season_trend(m)
    field_zone(m)
    costliest(m)
    (config.CHARTS_DIR / "alt_text.json").write_text(json.dumps(ALT, indent=2), encoding="utf-8")
    (config.CHARTS_DIR / "alt_text.md").write_text(
        "# Alt text\n\n" + "\n\n".join(f"## {k}\n\n{v}" for k, v in ALT.items()) + "\n",
        encoding="utf-8")
    print(f"\nWrote {len(ALT)} charts and alt text to {config.CHARTS_DIR}")


if __name__ == "__main__":
    main()
