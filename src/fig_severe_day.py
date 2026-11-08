"""
Severe-day operation of the economic baseline (D0) and the FFH-free design
(D4), with the cost composition of the representative designs D0-D4.

Two steps, so the figure can be redrawn without a solver:

  solve   (needs Gurobi) fixes the first stage of D0 and D4 to their archived
          designs, re-optimizes operation over the full scenario set
          (lambda = 0, MIPGap 0.2%), and writes the plotted series to
          FIGSEV_DATA (default fig_severe_day_data.json)
  render  draws the figure from that file and the archived cost records

Usage
  ROUTE_INPUTS=route52_inputs_v9.json FIGSEV_RES=campaign_v9rev_results.json \
      python3 fig_severe_day.py solve
  FIGSEV_RES=campaign_v9rev_results.json python3 fig_severe_day.py render

Panels: (a) battery energy of one block on the severe day, D0 and D4;
(b) depot and terminal load on the severe day; (c) delivered cabin heat by
source and band; (d) annual cost that differs between designs, D0-D4.
"""

import json
import os
import sys

RES = os.environ.get("FIGSEV_RES", "campaign_v9rev_results.json")
DATA = os.environ.get("FIGSEV_DATA", "fig_severe_day_data.json")
W = "severe"
BANDS = ["mild", "cold", "verycold", "extreme", "severe"]
DESIGNS = [("D0", "econ_lam0"), ("D1", "eps_0.70"), ("D2", "eps_0.20"),
           ("D3", "lam_5000"), ("D4", "eps_0.00")]


def solve():
    import route52_prototype as R
    import campaign_v5 as C

    runs = {r["label"]: r for r in json.load(open(RES))["runs"]}

    def trip_times(blk):
        out, cur = [], blk.pullout_h
        for i, tr in enumerate(blk.trips):
            out.append((cur, cur + tr.dur_h))
            cur = blk.dwells[i][2] if i < len(blk.dwells) else cur + tr.dur_h
        return out

    def run(label):
        d = C.design_from_record(runs[label])
        m = R.build_model(carbon_price_t=0.0)
        h = m._handles
        for k in range(len(R.BUS_CLASSES)):
            m.addConstr(h["x"][k] == d["x"][k])
        for n in R.SITES:
            for p in R.CH_CLASSES:
                m.addConstr(h["wch"][n, p] == d["wch"][(n, p)])
                m.addConstr(h["ysite"][n, p] == d["ysite"][(n, p)])
            for j in range(len(R.GRID_TIERS)):
                m.addConstr(h["ygrid"][n, j] == d["ygrid"][(n, j)])
        m.Params.OutputFlag = 0
        m.Params.MIPGap = 0.002
        m.Params.TimeLimit = 1800
        m.Params.Threads = int(os.environ.get("FIGSEV_THREADS", "8"))
        m.optimize()
        assert m.SolCount > 0, label
        return m

    out = {"note": "first stage fixed to the archived design; operation "
                   "re-optimized at lambda = 0, MIPGap 0.2%",
           "steps_h": None, "designs": {}}
    models = {lbl: run(lbl) for lbl in ("econ_lam0", "eps_0.00")}
    s4 = models["eps_0.00"]._scen[W]
    # block shown in panel (a): the one with most terminal charging in D4,
    # i.e. the block whose day the FFH-free design reshapes most
    b_show = max(range(R.N_BLOCKS),
                 key=lambda b: sum(v.X for (bb, n, t), v in s4["c"].items()
                                   if bb == b and n != "depot"))
    out["block"] = b_show
    out["steps_h"] = [R.T0 + (t + 0.5) * R.DT for t in R.STEPS]
    out["service_end_h"] = R.T_SVC_END
    for lbl, m in models.items():
        s = m._scen[W]
        hrs, val = [], []
        for i, (dep, arr) in enumerate(trip_times(R.BLOCKS[b_show])):
            hrs += [dep, arr]
            val += [s["Edep"][b_show, i].X, s["Earr"][b_show, i].X]
        cap = R.DERATE[W][0] * sum(R.BUS_CLASSES[k].batt_nom * s["z"][b_show, k].X
                                   for k in range(len(R.BUS_CLASSES)))
        depot, term = [], []
        for t in R.STEPS:
            dv = sum(s["c"][b, "depot", t].X for b in range(R.N_BLOCKS)
                     if (b, "depot", t) in s["c"])
            dv += sum(s["ppre"][b, t].X for b in range(R.N_BLOCKS)
                      if (b, t) in s["ppre"])
            tv = sum(v.X for (b, n, tt), v in s["c"].items()
                     if n != "depot" and tt == t)
            depot.append(round(dv, 2))
            term.append(round(tv, 2))
        heat = {w: {"electric": round(sum(v.X for v in m._scen[w]["qel"].values()), 1),
                    "ffh": round(sum(v.X for v in m._scen[w]["qff"].values()), 1)}
                for w in BANDS}
        out["designs"][lbl] = {"soc_h": hrs, "soc_kWh": [round(v, 2) for v in val],
                               "floor_kWh": round(R.S_LO * cap, 2),
                               "depot_kW": depot, "terminal_kW": term,
                               "heat_kWh": heat,
                               "mip_gap": round(m.MIPGap, 4)}
    json.dump(out, open(DATA, "w"), indent=1)
    print("wrote", DATA)


def render():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    BLUE, ORANGE, TEAL = "#1F4E79", "#C55A11", "#2E8B8B"
    GRAY = "#7F7F7F"
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
        "pdf.fonttype": 42, "font.size": 8, "axes.labelsize": 8.5,
        "xtick.labelsize": 7.5, "ytick.labelsize": 7.5, "legend.fontsize": 7,
        "axes.linewidth": 0.6, "axes.spines.top": False,
        "axes.spines.right": False, "axes.grid": True, "axes.grid.axis": "y",
        "grid.color": "#DDDDDD", "grid.linewidth": 0.4, "axes.axisbelow": True,
        "legend.frameon": False})
    D = json.load(open(DATA))
    runs = {r["label"]: r for r in json.load(open(RES))["runs"]}
    d0, d4 = D["designs"]["econ_lam0"], D["designs"]["eps_0.00"]

    fig, axes = plt.subplots(2, 2, figsize=(7.16, 4.6))
    (a, b), (c, d) = axes

    # (a) battery energy of the shown block, severe day
    a.plot(d0["soc_h"], d0["soc_kWh"], "-", color=BLUE, lw=1.0, label="(D0)")
    a.plot(d4["soc_h"], d4["soc_kWh"], "-", color=ORANGE, lw=1.0, label="(D4)")
    a.axhline(d0["floor_kWh"], color=GRAY, lw=0.6, ls=":")
    a.text(a.get_xlim()[0] if False else min(d0["soc_h"]), d0["floor_kWh"] + 8,
           "state-of-charge floor", fontsize=6.5, color=GRAY)
    a.set_xlabel("Hour of day")
    a.set_ylabel("Battery energy (kWh)")
    a.legend(loc="upper right")

    # (b) site load over the daily cycle, severe day
    hrs = D["steps_h"]
    b.step(hrs, d0["depot_kW"], where="mid", color=BLUE, lw=0.9, label="(D0) depot")
    b.step(hrs, d4["depot_kW"], where="mid", color=ORANGE, lw=0.9, label="(D4) depot")
    b.step(hrs, d4["terminal_kW"], where="mid", color=ORANGE, lw=0.8, ls="--",
           label="(D4) terminals")
    b.axvline(D["service_end_h"], color="#C9C9C9", lw=0.8)
    ticks = np.arange(6, 30, 4)
    b.set_xticks(ticks, [f"{int(h % 24):02d}" for h in ticks])
    b.set_xlabel("Hour (05:00 to 05:00 next day)")
    b.set_ylabel("Site load (kW)")
    b.legend(loc="upper left")

    # (c) delivered cabin heat by source and band
    x = np.arange(len(BANDS), dtype=float)
    wd = 0.36
    e0 = [d0["heat_kWh"][w]["electric"] for w in BANDS]
    f0 = [d0["heat_kWh"][w]["ffh"] for w in BANDS]
    e4 = [d4["heat_kWh"][w]["electric"] for w in BANDS]
    c.bar(x - wd / 2, e0, wd, color=BLUE, edgecolor="white", lw=0.4,
          label="Electric heat")
    c.bar(x - wd / 2, f0, wd, bottom=e0, color=ORANGE, edgecolor="white",
          lw=0.4, hatch="//", label="FFH heat")
    c.bar(x + wd / 2, e4, wd, color=BLUE, edgecolor="white", lw=0.4, alpha=0.55)
    c.set_xticks(x, ["Mild", "Cold", "Very\ncold", "Extreme", "Severe"])
    c.text(0.99, 0.97, "left bar: (D0)   right bar: (D4)", transform=c.transAxes,
           ha="right", va="top", fontsize=6.5, color=GRAY)
    c.set_ylabel("Cabin heat (kWh/day)")
    c.set_ylim(0, max(np.add(e0, f0).max(), max(e4)) * 1.3)
    c.legend(loc="upper left")

    # (d) annual cost that differs between designs (resource cost, no carbon)
    cats = ["Chargers and grid", "Electricity and demand charges",
            "FFH maintenance and diesel"]
    cols, hats = [TEAL, GRAY, ORANGE], ["", "..", "//"]
    vals = []
    for _, lbl in DESIGNS:
        cp = runs[lbl]["cost_parts"]
        vals.append(((cp["charger_site_capital"] + cp["grid_capital"]) / 1e3,
                     (cp["demand_charges"] + cp["electricity"]) / 1e3,
                     (cp["ffh_om"] + cp["diesel_cost"]) / 1e3))
    vals = np.array(vals)
    y = np.arange(len(DESIGNS), dtype=float)
    left = np.zeros(len(DESIGNS))
    for ci in range(3):
        d.barh(y, vals[:, ci], 0.55, left=left, color=cols[ci],
               edgecolor="white", lw=0.4, hatch=hats[ci], label=cats[ci])
        left += vals[:, ci]
    for yi, tot in zip(y, left):
        d.annotate(f"{tot:,.0f}", (tot, yi), textcoords="offset points",
                   xytext=(3, -3), fontsize=7)
    d.set_yticks(y, [f"({n})" for n, _ in DESIGNS])
    d.invert_yaxis()
    d.set_xlim(0, left.max() * 1.15)
    d.set_xlabel("Annual cost excluding buses (kCAD/yr)")
    d.grid(axis="x")
    d.grid(axis="y", visible=False)
    d.legend(loc="upper center", bbox_to_anchor=(0.45, -0.28), ncols=1)

    for ax, s in zip((a, b, c, d), "abcd"):
        ax.text(-0.02, 1.03, f"({s})", transform=ax.transAxes, fontsize=9,
                fontweight="bold", ha="right", va="bottom")
    fig.subplots_adjust(hspace=0.62, wspace=0.28)
    os.makedirs("ieee_figs", exist_ok=True)
    dirs = ["ieee_figs"] + [p for p in ("../overleaf-git/figures",) if os.path.isdir(p)]
    for dd in dirs:
        for ext in (("pdf", "png") if dd == "ieee_figs" else ("pdf",)):
            fig.savefig(f"{dd}/fig_severe_day.{ext}", dpi=300 if ext == "png" else None,
                        bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
    print("wrote fig_severe_day ->", ", ".join(dirs))


if __name__ == "__main__":
    {"solve": solve, "render": render}[sys.argv[1] if len(sys.argv) > 1 else "render"]()
