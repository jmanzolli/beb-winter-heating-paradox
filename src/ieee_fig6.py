"""
Figure 6 (paper Fig. 3 slot): Route 52 operating diagnostics, restyled to the
post-audit IEEE identity. Solves the carbon-price design
(1% gap; diagnostics figure, not a certified-cost claim), then renders:
(a) severe-day SoC, (b) severe-day site load over the full daily cycle,
(c) heat-source split per band, (d) differentiating annual costs.
Outputs: ieee_figs/fig6_{1col,2col}.{svg,pdf,png}
"""

import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import gurobipy as gp

import route52_prototype as R

BLUE, TEAL, ORANGE = "#1F4E79", "#2E8B8B", "#C55A11"
GRAY, LGRAY = "#7F7F7F", "#C9C9C9"
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none",
    "font.size": 8, "axes.labelsize": 8.5, "xtick.labelsize": 8,
    "ytick.labelsize": 8, "legend.fontsize": 7.5,
    "axes.linewidth": 0.6, "axes.spines.top": False,
    "axes.spines.right": False, "axes.grid": True, "axes.grid.axis": "y",
    "grid.color": "#DDDDDD", "grid.linewidth": 0.4, "axes.axisbelow": True,
    "legend.frameon": False, "figure.facecolor": "white",
    "axes.facecolor": "white", "savefig.facecolor": "white",
})

def solve(depot_only=False):
    m = R.build_model()
    if depot_only:
        h = m._handles
        for n in R.SITES:
            if n == "depot":
                continue
            for p in R.CH_CLASSES:
                m.addConstr(h["wch"][n, p] == 0)
            for j in range(len(R.GRID_TIERS)):
                m.addConstr(h["ygrid"][n, j] == 0)
    m.Params.OutputFlag = 0
    m.Params.MIPGap = 0.01
    m.Params.TimeLimit = 900
    m.optimize()
    assert m.SolCount > 0
    return m

print("solving carbon-price design ...")
m_opt = solve()
# cost composition for three frontier designs, read from the campaign record
_R = json.load(open("campaign_v5_results.json"))
_runs = {r["label"]: r for r in _R["runs"]}
DESIGNS = [("Economic", "econ_lam0"), ("First transition", "eps_0.20"),
           ("Zero emission", "eps_0.00")]

W = "severe"
BANDS = ["mild", "cold", "verycold", "extreme", "severe"]
BAND_LBL = ["Mild", "Cold", "Very\ncold", "Extreme", "Severe"]

def trip_times(blk):
    out, cur = [], blk.pullout_h
    for i, tr in enumerate(blk.trips):
        out.append((cur, cur + tr.dur_h))
        cur = blk.dwells[i][2] if i < len(blk.dwells) else cur + tr.dur_h
    return out

def sawtooth(m, b):
    s = m._scen[W]
    hrs, val = [], []
    for i, (dep, arr) in enumerate(trip_times(R.BLOCKS[b])):
        hrs += [dep, arr]; val += [s["Edep"][b, i].X, s["Earr"][b, i].X]
    return hrs, val

def site_load(m, n):
    s = m._scen[W]
    out = []
    for t in R.STEPS:
        v = sum(s["c"][b, n, t].X for b in range(R.N_BLOCKS) if (b, n, t) in s["c"])
        if n == "depot":
            v += sum(s["ppre"][b, t].X for b in range(R.N_BLOCKS) if (b, t) in s["ppre"])
        out.append(v)
    return out

def heat_split(m, w):
    s = m._scen[w]
    return (sum(v.X for v in s["qel"].values()),
            sum(v.X for v in s["qff"].values()))

def cost_parts(m):
    h = m._handles
    K = range(len(R.BUS_CLASSES))
    ch = (R.CRF_CH * sum(R.charger_cost(p) * h["wch"][n, p].X
                         for n in R.SITES for p in R.CH_CLASSES)
          + R.CRF_CH * R.SITE_FIXED_COST * sum(
              h["ysite"][n, p].X for n in R.SITES for p in R.CH_CLASSES
              if n != "depot")
          + R.CRF_GRID * sum(R.GRID_TIER_COST[j] * h["ygrid"][n, j].X
                             for n in R.SITES for j in range(len(R.GRID_TIERS))))
    elec = h["demand_annual"].getValue()
    ffh = R.FFH_ANNUAL_OM * sum(h["x"][k].X for k in K if R.BUS_CLASSES[k].ffh)
    for w, (_, days) in R.SCEN.items():
        s = m._scen[w]
        elec += days * s["energy_cost"].getValue()
        ffh += days * (R.DIESEL_PRICE
                       + R.CARBON_PRICE_T * R.CO2_PER_L / 1000.0) * s["D"].X
    return ch / 1e3, elec / 1e3, ffh / 1e3

c_opt = m_opt._scen[W]["c"]
b_show = max(range(R.N_BLOCKS),
             key=lambda b: sum(v.X for (bb, n, t), v in c_opt.items()
                               if bb == b and n != "depot"))

def panel_label(ax, s):
    ax.text(0.5, 1.03, s, transform=ax.transAxes, fontsize=9,
            fontweight="bold", va="bottom", ha="center")

def render(width, name):
    if width < 5:
        fig, axes = plt.subplots(4, 1, figsize=(width, 7.4))
        a, b, c, d = axes
    else:
        fig, axes = plt.subplots(2, 2, figsize=(width, 3.4))
        (a, b), (c, d) = axes

    # (a) SoC severe day
    for m, col, ls, lab in [(m_opt, BLUE, "-", "Carbon-price design")]:
        hrs, soc = sawtooth(m, b_show)
        a.plot(hrs, soc, ls, color=col, lw=1.0, label=lab)
    cn = R.DERATE[W][0] * sum(R.BUS_CLASSES[k].batt_nom
                              * m_opt._scen[W]["z"][b_show, k].X
                              for k in range(len(R.BUS_CLASSES)))
    a.axhline(R.S_LO * cn, color=GRAY, lw=0.6, ls=":")
    a.annotate("arrival-reserve floor", xy=(0.02, 0.05),
               xycoords="axes fraction", fontsize=7.5, color=GRAY)
    a.set_xlabel("Hour of day"); a.set_ylabel("Battery energy [kWh]")
    a.legend(loc="upper right")

    # (b) site load, full daily cycle
    hrs_full = [R.T0 + (t + 0.5) * R.DT for t in R.STEPS]
    loads = {n: site_load(m_opt, n) for n in R.SITES}
    active = [n for n in R.SITES if max(loads[n]) > 1.0]
    styles = [(BLUE, "-"), (TEAL, "--"), (ORANGE, ":")]
    for i, n in enumerate(sorted(active, key=lambda n: -max(loads[n]))):
        col, ls = styles[i % len(styles)]
        b.step(hrs_full, loads[n], where="mid", color=col, ls=ls, lw=0.9,
               label="Depot" if n == "depot" else n)
    b.axvline(R.T_SVC_END, color=LGRAY, lw=0.8)
    ticks = np.arange(6, 30, 4)
    b.set_xticks(ticks, [f"{int(h % 24):02d}" for h in ticks])
    b.set_xlabel("Hour (wraps past midnight)")
    b.set_ylabel("Site load [kW]")
    b.legend(loc="upper left")

    # (c) heat split per band, both configs side by side
    x = np.arange(len(BANDS), dtype=float)
    wd = 0.56
    for j, (m, off) in enumerate([(m_opt, 0.0)]):
        els, ffs = zip(*(heat_split(m, w_) for w_ in BANDS))
        xs = x + off
        c.bar(xs, els, wd, color=BLUE, edgecolor="white", lw=0.4,
              label="Electric heat" if j == 0 else None)
        c.bar(xs, ffs, wd, bottom=els, color=ORANGE, edgecolor="white",
              lw=0.4, hatch="//" if True else None,
              label="FFH heat" if j == 0 else None)
    c.set_xticks(x, BAND_LBL, fontsize=7.5)
    c.set_ylabel("Heat delivered [kWh/day]")
    c.set_ylim(0, c.get_ylim()[1] * 1.32)
    c.legend(loc="upper left", ncols=2, columnspacing=0.9)

    # (d) differentiating annual costs
    cats = ["Charging + grid capital", "Electricity", "FFH (O&M + diesel + CO$_2$)"]
    cols = [TEAL, GRAY, ORANGE]
    hats = ["", "..", "//"]
    def _parts(lbl):
        cp = _runs[lbl]["cost_parts"]
        return (( cp["charger_site_capital"] + cp["grid_capital"]) / 1e3,
                (cp["demand_charges"] + cp["electricity"]) / 1e3,
                (cp["ffh_om"] + cp["diesel_cost"] + cp["carbon_cost"]) / 1e3)
    y = np.arange(len(DESIGNS), dtype=float)
    vals = np.array([_parts(l) for _, l in DESIGNS])
    lefts = np.zeros(len(DESIGNS))
    for ci in range(3):
        d.barh(y, vals[:, ci], 0.5, left=lefts, color=cols[ci],
               edgecolor="white", lw=0.4, hatch=hats[ci], label=cats[ci])
        lefts += vals[:, ci]
    for yi, tot in zip(y, lefts):
        d.annotate(f"{tot:,.0f}", (tot, yi), textcoords="offset points",
                   xytext=(4, -3), fontsize=7.5)
    d.set_yticks(y, [n.replace(" ", "\n") for n, _ in DESIGNS], fontsize=7)
    d.invert_yaxis()
    d.set_xlim(0, lefts.max() * 1.14)
    d.set_xlabel("Differentiating annual cost [kCAD/yr]")
    d.grid(axis="x"); d.grid(axis="y", visible=False)
    d.legend(loc="upper center", bbox_to_anchor=(0.42, -0.34),
             ncols=1, fontsize=7, handlelength=1.4)

    for ax, s in zip((a, b, c, d), "abcd"):
        panel_label(ax, f"({s})")
    fig.subplots_adjust(hspace=0.52 if width < 5 else 0.72,
                        wspace=0.30)
    for ext in ("svg", "pdf", "png"):
        fig.savefig(f"ieee_figs/{name}.{ext}",
                    dpi=600 if ext == "png" else None,
                    bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)

render(3.5, "fig6_1col")
render(7.16, "fig6_2col")
print("saved fig6_{1col,2col}")
