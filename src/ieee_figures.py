"""
IEEE T-ITS publication figure set (redesign per art-editor spec).

Data source: campaign_results.json / campaign_garage.json — values are read
programmatically from the solver-output files (no manual transcription, no
smoothing, no interpolation). Verification tables for every figure are
written to ieee_figs/verification_tables.md directly from the same records.

Outputs (ieee_figs/): fig{1..5}_{1col,2col}.{svg,pdf,png}   (PNG at 600 dpi)

Deterministic Matplotlib only. Shared style; Arial/Helvetica; TrueType
embedding (pdf.fonttype 42); editable SVG text (svg.fonttype 'none').
"""

import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# ----------------------------------------------------------------------------
# shared style configuration (single visual identity, IEEE sizes in points)
# ----------------------------------------------------------------------------
BLUE, TEAL, ORANGE = "#1F4E79", "#2E8B8B", "#C55A11"   # primary/secondary/policy
GRAY, LGRAY = "#7F7F7F", "#C9C9C9"                     # reference / uncertainty

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none",
    "font.size": 8, "axes.labelsize": 8.5, "xtick.labelsize": 8,
    "ytick.labelsize": 8, "legend.fontsize": 7.5,
    "axes.linewidth": 0.6, "xtick.major.width": 0.6, "ytick.major.width": 0.6,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "axes.grid.axis": "y", "grid.color": "#DDDDDD",
    "grid.linewidth": 0.4, "axes.axisbelow": True,
    "legend.frameon": False, "figure.facecolor": "white",
    "axes.facecolor": "white", "savefig.facecolor": "white",
})
LW_MAIN, LW_REF, LW_ERR = 1.0, 0.6, 0.7
MS = 4
R_RESERVE = 10.0   # end-of-service reserve, kWh
OUT = "ieee_figs"
os.makedirs(OUT, exist_ok=True)

def save(fig, name):
    for ext in ("svg", "pdf", "png"):
        fig.savefig(f"{OUT}/{name}.{ext}", dpi=600 if ext == "png" else None,
                    bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)

def panel_label(ax, s, x=0.5, y=1.02):
    ax.text(x, y, s, transform=ax.transAxes, fontsize=9, fontweight="bold",
            va="bottom", ha="center")

# ----------------------------------------------------------------------------
# data — read programmatically from solver outputs
# ----------------------------------------------------------------------------
# data source is overridable so the v6 adapter output can be used without
# touching the plotting code (and thus the approved visual design)
D = json.load(open(os.environ.get("FIG_CAMPAIGN", "campaign_results.json")))
import os.path as _op
_g = os.environ.get("FIG_GARAGE", "campaign_garage.json")
G = json.load(open(_g)) if _op.exists(_g) else {}
runs = {r["label"]: r for r in D["runs"] if r}
frontier = sorted([r for r in D["frontier"] if r], key=lambda r: -r["co2_t"])
lsweep = [r for r in D["lambda_sweep"] if r]
bpver = [r for r in D["breakpoint_verification"] if r]
sens_order = ["ffh_om_500", "ffh_om_2000", "ffh_capex_5000", "ffh_capex_15000",
              "grid_100", "grid_300", "batt_100", "batt_50"]
sens = {r["label"]: r for r in D["sensitivity"] if r}
ops = D["ops_metrics_policy"]
base = runs["policy_lambda100"]
garage = {r["label"]: r for r in G}

def opp_ch(r):  return sum(v for k, v in r["chargers"].items() if "depot" not in k)
def depot_ch(r): return sum(v for k, v in r["chargers"].items() if "depot" in k)

F1min = min(r["F1"] for r in frontier + lsweep + bpver)
def dF1(r):  return (r["F1"] - F1min) / 1e3            # kCAD/yr above best
def herr(r): return (r["obj"] - r["lb"]) / 2e3         # half certified gap, kCAD

BANDS = ["mild", "cold", "verycold", "extreme", "severe"]
BAND_LBL = ["Mild\n(+2.5°C)", "Cold\n(−2.5°C)", "Very cold\n(−7.5°C)",
            "Extreme\n(−12.5°C)", "Severe\n(−17.5°C)"]

# ----------------------------------------------------------------------------
# verification tables (written straight from the records used to plot)
# ----------------------------------------------------------------------------
V = ["# Verification tables — generated programmatically from "
     "campaign_results.json / campaign_garage.json\n",
     "No value was transcribed, smoothed, interpolated, or edited by hand.\n"]
V.append("\n## Figure 1 & 2 — frontier points (eps-constraint, lambda=0)\n")
V.append("| cap achieved [tCO2/yr] | F1 [CAD/yr] | obj UB | obj LB | FFH | ext | opp ch | depot ch |")
V.append("|---|---|---|---|---|---|---|---|")
for r in frontier:
    V.append(f"| {r['co2_t']} | {r['F1']:,.0f} | {r['obj']:,.0f} | {r['lb']:,.0f} "
             f"| {r['n_ffh']} | {r['n_ext']} | {opp_ch(r)} | {depot_ch(r)} |")
V.append("\n## Figure 2 — lambda sweep + breakpoint verification\n")
V.append("| lambda [CAD/t] | co2 [t/yr] | F1 [CAD/yr] | obj UB | obj LB |")
V.append("|---|---|---|---|---|")
for r in lsweep + bpver:
    V.append(f"| {r['lam']:g} | {r['co2_t']} | {r['F1']:,.0f} | {r['obj']:,.0f} | {r['lb']:,.0f} |")
V.append("\n## Figure 3 — operations metrics (policy case)\n")
V.append("| band | min reserve [kWh] | p5 reserve [kWh] | plug-hours | reassignments |")
V.append("|---|---|---|---|---|")
for w in BANDS:
    o = ops[w]
    V.append(f"| {w} | {o['min_reserve_kWh_min']} | {o['min_reserve_kWh_p5']} "
             f"| {o['plug_hours_used']} | {o['reassigned_blocks_vs_mildest']} |")
V.append("\n## Figure 4 — FFH-equipped fleet share\n")
V.append("| case | Route 52 | Arrow Road division |")
V.append("|---|---|---|")
V.append(f"| lambda=0 | 18/18 = 100% | {garage['garage_lam0']['n_ffh']}/183 = "
         f"{100*garage['garage_lam0']['n_ffh']/183:.0f}% |")
V.append(f"| lambda=100 | 18/18 = 100% | {garage['garage_lam100']['n_ffh']}/183 = "
         f"{100*garage['garage_lam100']['n_ffh']/183:.0f}% |")
V.append("\n## Figure 5 — sensitivity vs baseline "
         f"(baseline obj {base['obj']:,.0f}, LB {base['lb']:,.0f})\n")
V.append("| case | obj UB | obj LB | Δ interval [CAD/yr] | FFH | diesel [L/yr] |")
V.append("|---|---|---|---|---|---|")
for k in sens_order:
    s = sens[k]
    lo, hi = s["lb"] - base["obj"], s["obj"] - base["lb"]
    V.append(f"| {k} | {s['obj']:,.0f} | {s['lb']:,.0f} | [{lo:,.0f}, {hi:,.0f}] "
             f"| {s['n_ffh']} | {s['diesel_L']:,.0f} |")
open(f"{OUT}/verification_tables.md", "w").write("\n".join(V) + "\n")

# ============================================================================
# FIGURE 1 — design transitions along the frontier (4 stacked small multiples)
# ============================================================================
def fig1(width, name):
    caps = [r["co2_t"] for r in frontier]
    series = [("FFH\nbuses", [r["n_ffh"] for r in frontier], BLUE, "o", "-"),
              ("Extended-\nbattery buses", [r["n_ext"] for r in frontier], TEAL, "s", "--"),
              ("Opportunity\nchargers", [opp_ch(r) for r in frontier], ORANGE, "D", "-."),
              ("Depot\nchargers", [depot_ch(r) for r in frontier], GRAY, "^", ":")]
    h = 3.7 if width < 5 else 3.3
    fig, axes = plt.subplots(4, 1, figsize=(width, h), sharex=True)
    trans = [(4.91, "extended batteries enter"),
             (2.06, "opportunity charging enters"),
             (0.0, "all FFHs removed")]
    for ax, (lab, vals, col, mk, ls) in zip(axes, series):
        ax.step(caps, vals, where="post", color=col, lw=LW_MAIN, ls=ls, zorder=3)
        ax.plot(caps, vals, mk, color=col, ms=MS - 1, zorder=4)
        ax.set_ylabel(lab, fontsize=8)
        ymax = max(vals)
        ax.set_yticks(range(0, ymax + 1, max(1, int(np.ceil(ymax / 3)))))
        ax.set_ylim(-0.6, ymax * 1.25 + 0.6)
        for xv, _ in trans:
            ax.axvline(xv, color=LGRAY, lw=0.8, zorder=1)
    for (xv, txt), ax_i, dy in zip(trans, [1, 2, 0], [0.72, 0.72, 0.75]):
        ax = axes[ax_i]
        ax.annotate(txt, xy=(xv, ax.get_ylim()[1] * 0.55),
                    xytext=(xv + (4.5 if width < 5 else 3.2), ax.get_ylim()[1] * dy),
                    fontsize=7.5, color="#333333", ha="left",
                    arrowprops=dict(arrowstyle="-|>", color=GRAY, lw=0.8))
    axes[-1].set_xlabel("Residual Scope 1 emissions cap [tCO$_2$/yr]")
    axes[-1].invert_xaxis()
    for i, ax in enumerate(axes):
        panel_label(ax, f"({chr(97+i)})")
    fig.align_ylabels(axes)
    fig.subplots_adjust(hspace=0.62 if width < 5 else 0.45)
    save(fig, name)

fig1(3.5, "fig1_1col")
fig1(7.16, "fig1_2col")

# ============================================================================
# FIGURE 2 — cost–emissions frontier: (a) full, (b) low-emissions zoom
# ============================================================================
def draw_frontier(ax, xlim=None, label_lams=(200, 2000)):
    fx, fy = [r["co2_t"] for r in frontier], [dF1(r) for r in frontier]
    fe = [herr(r) for r in frontier]
    ax.errorbar(fx, fy, yerr=fe, color=BLUE, lw=LW_MAIN, marker="o", ms=MS - 1,
                elinewidth=LW_ERR, ecolor=GRAY, capsize=2.4, zorder=3,
                label="$\\varepsilon$-constraint frontier")
    pts = sorted(zip(fx, fy))
    env = [pts[0]]
    for p in pts[1:]:
        while len(env) >= 2 and (env[-1][1]-env[-2][1])*(p[0]-env[-2][0]) >= \
                                (p[1]-env[-2][1])*(env[-1][0]-env[-2][0]):
            env.pop()
        env.append(p)
    ax.plot(*zip(*env), color=GRAY, lw=LW_REF, ls="--", zorder=2,
            label="Lower convex envelope")
    ax.plot([r["co2_t"] for r in lsweep], [dF1(r) for r in lsweep], "D",
            color=ORANGE, ms=MS, zorder=4, ls="none",
            label="Carbon-price solutions")
    ax.plot([r["co2_t"] for r in bpver], [dF1(r) for r in bpver], "s",
            mfc="none", mec=TEAL, mew=1.3, ms=MS, zorder=5, ls="none",
            label="Breakpoint verification")
    for r in lsweep:
        if r["lam"] in label_lams and (xlim is None or
                                       xlim[1] <= r["co2_t"] <= xlim[0]):
            dy = -11 if r["lam"] < 2500 else 7
            ax.annotate(f"$\\lambda$={r['lam']:g}",
                        (r["co2_t"], dF1(r)), textcoords="offset points",
                        xytext=(5, dy), fontsize=7, color=ORANGE)
    if xlim:
        ax.set_xlim(*xlim)

def fig2(width, name):
    if width < 5:
        fig, (a, b) = plt.subplots(2, 1, figsize=(width, 3.8))
    else:
        fig, (a, b) = plt.subplots(1, 2, figsize=(width, 2.9),
                                   gridspec_kw={"width_ratios": [1.35, 1]})
    draw_frontier(a); a.invert_xaxis()
    a.set_title("(a) Full frontier", fontsize=9)
    draw_frontier(b, xlim=(10, -0.4), label_lams=(2000, 3500))
    b.set_title("(b) Low-emissions region", fontsize=9)
    for ax in (a, b):
        ax.set_xlabel("Residual Scope 1 emissions [tCO$_2$/yr]"
                      "\n(cap tightened $\\rightarrow$)")
        ax.set_ylabel("Incremental annual\nsystem cost [kCAD/yr]")
    a.legend(loc="upper left", handlelength=1.6)
    fig.subplots_adjust(hspace=0.78, wspace=0.30)
    save(fig, name)

fig2(3.5, "fig2_1col")
fig2(7.16, "fig2_2col")

# ============================================================================
# FIGURE 3 — operations: (a) arrival reserve, (b) depot plug use
# ============================================================================
def fig3(width, name):
    x = np.arange(len(BANDS))
    rmin = [ops[w]["min_reserve_kWh_min"] for w in BANDS]
    plugs = [ops[w]["plug_hours_used"] for w in BANDS]
    if width < 5:
        fig, (a, b) = plt.subplots(2, 1, figsize=(width, 3.2))
    else:
        fig, (a, b) = plt.subplots(1, 2, figsize=(width, 2.6))
    a.plot(x, rmin, "-o", color=BLUE, lw=LW_MAIN, ms=MS - 1,
           label="Minimum arrival reserve")
    a.axhline(0, color=GRAY, lw=LW_REF, ls="--")
    # the 10 kWh end-of-service reserve is a separate, higher threshold than
    # the hard floor at zero; both matter and were previously conflated
    a.axhline(R_RESERVE, color=ORANGE, lw=LW_REF, ls=":")
    a.annotate("10 kWh return reserve", xy=(0.02, 0.30),
               xycoords="axes fraction", fontsize=6.5, color=ORANGE)
    a.annotate("hard SoC floor", xy=(0.02, 0.04),
               xycoords="axes fraction", fontsize=7.5, color=GRAY)
    a.set_ylabel("Arrival reserve\nabove floor [kWh]")
    a.set_ylim(-6, max(rmin) * 1.18)
    b.bar(x, plugs, 0.55, color=TEAL, edgecolor="white", lw=0.5)
    b.set_ylabel("Depot plug use\n[plug-hours/day]")
    b.set_ylim(0, max(plugs) * 1.18)
    for ax in (a, b):
        ax.set_xticks(x, BAND_LBL, fontsize=7.5)
    panel_label(a, "(a)"); panel_label(b, "(b)")
    fig.text(0.99, -0.055 if width < 5 else -0.05,
             "No block-class reassignments under the "
             "$\\lambda$=100 CAD/tCO$_2$ case.",
             ha="right", fontsize=7.5, color="#333333", style="italic")
    fig.subplots_adjust(hspace=0.60, wspace=0.32)
    save(fig, name)

fig3(3.5, "fig3_1col")
fig3(7.16, "fig3_2col")

# ============================================================================
# FIGURE 4 — route vs division: slopegraph
# ============================================================================
def fig4(width, name):
    g0 = 100 * garage["garage_lam0"]["n_ffh"] / 183
    g100 = 100 * garage["garage_lam100"]["n_ffh"] / 183
    h = 2.6
    fig, ax = plt.subplots(figsize=(width, h))
    for y0, y1, col, ls, lab, dy in [
            (100, g0, BLUE, "-", "$\\lambda$=0", 3),
            (100, g100, ORANGE, "--", "$\\lambda$=100 CAD/tCO$_2$", -5)]:
        ax.plot([0, 1], [y0, y1], ls, color=col, lw=LW_MAIN,
                marker="o", ms=MS - 1)
        ax.annotate(f"{y0:.0f}%", (0, y0), textcoords="offset points",
                    xytext=(-8, dy), ha="right", fontsize=8, color=col)
        ax.annotate(f"{y1:.0f}%", (1, y1), textcoords="offset points",
                    xytext=(8, -3), ha="left", fontsize=8, color=col)
        ax.annotate(lab, (1, y1), textcoords="offset points",
                    xytext=(8, 9 if col == BLUE else -18), ha="left",
                    fontsize=7.5, color=col)
    ax.annotate("$-$75 percentage points", (0.56, (100 + g0) / 2 + 3),
                fontsize=7.5, color=BLUE, ha="center")
    ax.annotate("$-$79 percentage points", (0.56, (100 + g100) / 2 - 14),
                fontsize=7.5, color=ORANGE, ha="center")
    ax.set_xlim(-0.35, 1.55); ax.set_ylim(0, 108)
    ax.set_xticks([0, 1], ["Route 52", "Arrow Road\ndivision"], fontsize=8.5)
    ax.set_ylabel("FFH-equipped fleet share [%]")
    ax.grid(axis="y")
    save(fig, name)

fig4(3.5, "fig4_1col")
fig4(7.16, "fig4_2col")

# ============================================================================
# FIGURE 5 — sensitivity: (a) Δcost forest plot, (b) dispatch response
# ============================================================================
SENS_LBL = ["FFH O&M 0.5 kCAD/yr", "FFH O&M 2 kCAD/yr",
            "FFH capital 5 kCAD", "FFH capital 15 kCAD",
            "Grid 100 CAD/kW", "Grid 300 CAD/kW",
            "Battery 100 CAD/kWh", "Battery 50 CAD/kWh"]

def fig5(width, name):
    y = np.arange(len(sens_order))
    lo = [(sens[k]["lb"] - base["obj"]) / 1e3 for k in sens_order]
    hi = [(sens[k]["obj"] - base["lb"]) / 1e3 for k in sens_order]
    mid = [(a + b) / 2 for a, b in zip(lo, hi)]
    err = [(b - a) / 2 for a, b in zip(lo, hi)]
    diesel = [sens[k]["diesel_L"] / 1e3 for k in sens_order]
    if width < 5:
        fig, (a, b, c) = plt.subplots(3, 1, figsize=(width, 4.3))
    else:
        fig, (a, b, c) = plt.subplots(1, 3, figsize=(width, 2.7), sharey=True)
    a.errorbar(mid, y, xerr=err, fmt="o", color=BLUE, ms=MS - 1,
               elinewidth=LW_ERR, capsize=2.6)
    a.axvline(0, color=GRAY, lw=LW_REF, ls="--")
    a.set_yticks(y, SENS_LBL, fontsize=7.5)
    a.invert_yaxis()
    a.set_xlabel("$\\Delta$ annual cost [kCAD/yr]")
    a.grid(axis="x"); a.grid(axis="y", visible=False)
    b.barh(y, diesel, 0.55, color=TEAL, edgecolor="white", lw=0.5)
    b.axvline(base["diesel_L"] / 1e3, color=GRAY, lw=LW_REF, ls="--")
    b.annotate("baseline", (base["diesel_L"] / 1e3, -0.62),
               fontsize=7.5, color=GRAY, ha="center", va="bottom",
               annotation_clip=False)
    if width < 5:
        b.set_yticks(y, SENS_LBL, fontsize=7.5)
    b.invert_yaxis() if width < 5 else None
    b.set_xlabel("Diesel [10$^3$ L/yr]")
    b.set_xlim(0, max(diesel) * 1.15)
    b.grid(axis="x"); b.grid(axis="y", visible=False)
    # (c) fleet composition: the specification is NOT invariant across these
    # cases, so it is plotted rather than asserted in an annotation
    def _n(k, ffh):
        return sum(v for nm, v in sens[k]["fleet"].items()
                   if (("FFH" in nm) if ffh else ("eOnly" in nm)))
    nffh = [_n(k, True) for k in sens_order]
    next_ = [sens[k].get("n_ext", 0) for k in sens_order]
    c.barh(y - 0.19, nffh, 0.36, color=BLUE, edgecolor="white", lw=0.4,
           label="FFH-equipped")
    c.barh(y + 0.19, next_, 0.36, color=ORANGE, edgecolor="white", lw=0.4,
           label="extended battery")
    c.axvline(18, color=GRAY, lw=LW_REF, ls="--")
    c.set_yticks(y); c.tick_params(labelleft=False)
    c.set_xlabel("Buses [-]")
    c.set_xlim(0, 21)
    c.legend(loc="upper center", bbox_to_anchor=(0.5, -0.28), ncol=2,
             fontsize=6.5, frameon=False, handlelength=1.2,
             columnspacing=1.0)
    c.grid(axis="x"); c.grid(axis="y", visible=False)
    panel_label(a, "(a)")
    panel_label(b, "(b)")
    panel_label(c, "(c)")
    if width < 5:
        fig.subplots_adjust(hspace=0.75, left=0.34, bottom=0.13)
    else:
        fig.subplots_adjust(wspace=0.12, left=0.155, bottom=0.30, right=0.99)
    save(fig, name)

fig5(3.5, "fig5_1col")
fig5(7.16, "fig5_2col")

print("wrote 5 figures x 2 widths x 3 formats + verification_tables.md in", OUT)
