"""
Figures of main_2.tex redrawn for the revision of 2026-11 (review of
2026-11-09), in the house style of make_figs_m2.py. Overwrites, in
../overleaf-git/figures/m2/:

  fig_robust        cost of removing the heaters by sensitivity variant, sorted
                    (a), and heaters kept against the installed heater price (b)
  fig4_frontier     frontier with segments named by what is added (a) and
                    annual cost by component, designs D0-D4 (b)
  fig5_uncertainty  reliability protocol v10: days above the reserve and days
                    with every trip completed, by band
  fig_severe_day    panels (a) battery energy and (b) site load only
  fig_division      four plans: cost interval, heater-equipped buses, emissions
  figS_routes       per-route heater share with zero labels and Route 52 marked

Inputs: v9rev/ (archives), v10rev/results_v10.json, v10rev/div10_*.json.
Usage (from code/): python3 make_figs_m2_rev2.py
"""
import json
import os

import numpy as np

import make_figs_m2 as M
from make_figs_m2 import (BANDS, BLBL, BLUE, BOX, CM, GREEN, GRID, INK, MUTED, OCHRE,
                          ROSE, W1, W2, R, load, panel, plt, runs, save)

V10 = json.load(open("v10rev/results_v10.json"))
REL = V10["reliability"]


# ------------------------------------------------------------- robustness
def fig_robust():
    rows = []
    for lab, fn in M.VARIANTS:
        rr = runs("campaign_v9_results.json") if fn is None else runs(fn)
        e, z = rr["econ_lam0"], rr["eps_0.00"]
        rows.append((lab, 100 * (z["F1"] - e["F1"]) / e["F1"], e["co2_t"]))
    base = rows[0]
    rest = sorted(rows[1:], key=lambda r: r[1])
    rows = rest
    n = len(rows)
    y = np.arange(n)
    fig, (a, b) = plt.subplots(1, 2, figsize=(W2, 7.2 * CM),
                               gridspec_kw={"width_ratios": [1.55, 1], "wspace": 0.32})
    a.grid(axis="y", visible=False)
    a.grid(axis="x", color=GRID, lw=0.6)
    prem = np.array([r[1] for r in rows])
    a.barh(y, prem - base[1], 0.62, left=base[1],
           color=[ROSE if v > base[1] else BLUE for v in prem], edgecolor="white", lw=0.5)
    a.axvline(base[1], color=INK, lw=0.8)
    for yi, r in zip(y, rows):
        off = 0.015 if r[1] >= base[1] else -0.015
        a.text(r[1] + off, yi, f"{r[1]:.2f}", va="center", fontsize=6.8, color=MUTED,
               ha="left" if r[1] >= base[1] else "right")
    a.set_yticks(y, [r[0] for r in rows])
    a.set_xlim(prem.min() - 0.16, prem.max() + 0.16)
    a.set_xlabel("Cost of removing all heaters (% of annual fleet cost)")
    a.text(base[1] - 0.02, n - 0.45, f"Base case {base[1]:.2f}%", fontsize=7, ha="right",
           va="bottom", color=INK)
    a.set_ylim(-0.6, n + 0.2)
    panel(a, "a", x=-0.62)
    cap = V10["capex"]["runs"]
    px = sorted(float(k) for k in cap)
    xs = [0.0, 5.0, 10.0, 12.5] + [p / 1e3 for p in px]
    arc = runs("campaign_v9rev_results.json")
    ys = [18, 18, 18, 18] + [cap[k]["n_ffh"] for k in sorted(cap, key=float)]
    for lbl, xv in (("ffh_capex_5000", 5.0), ("ffh_capex_10000", 10.0),
                    ("ffh_capex_12500", 12.5)):
        if lbl in arc:
            ys[xs.index(xv)] = arc[lbl]["n_ffh"]
    b.plot(xs, ys, "o", color=OCHRE, ms=5, mec="white", mew=0.6, zorder=3)
    b.step(xs, ys, where="post", color=OCHRE, lw=1.0, zorder=2)
    sw = V10["capex"]["envelope"]
    b.axvline(18.2, color=MUTED, lw=0.8, ls=(0, (2, 2)))
    b.text(18.6, 12.2, "best-known\nswitch, 18.2", fontsize=6.8, color=MUTED, va="center")
    b.axvspan(3.0, 5.0, color="#EFEFEF", zorder=0, lw=0)
    b.text(4.0, 3.2, "retail unit\nprice", fontsize=6.8, color=MUTED, ha="center")
    b.set_xlim(-1, 31.5)
    b.set_ylim(0, 20)
    b.set_yticks([0, 6, 12, 18])
    b.set_xlabel("Installed cost per heater (kCAD)")
    b.set_ylabel("Heaters kept (of 18 buses)")
    panel(b, "b", x=-0.14)
    save(fig, "fig_robust")


# ------------------------------------------------------------- frontier
def fig_frontier():
    f0 = R["econ_lam0"]["F1"]
    pool = [r for l, r in R.items()
            if l == "econ_lam0" or l.startswith(("eps_", "lam_", "bp_lam_"))]
    nd = [p for p in pool if not any(
        (q["co2_t"] <= p["co2_t"] and q["F1"] < p["F1"] - 1e-6) or
        (q["co2_t"] < p["co2_t"] - 1e-6 and q["F1"] <= p["F1"]) for q in pool)]
    nd.sort(key=lambda r: r["co2_t"])
    fig, (ax, d) = plt.subplots(1, 2, figsize=(W2, 7.2 * CM),
                                gridspec_kw={"width_ratios": [1.45, 1], "wspace": 0.3})
    d1, d2 = R["eps_0.70"]["co2_t"], R["eps_0.20"]["co2_t"]
    top = 80
    for x0, x1, lab, c, tx, ty, ha in (
            (-0.6, d2, "+ terminal power,\nextended battery", "#EDEDED", -0.3, top - 2, "left"),
            (d2, d1, "+ electric-only buses,\nterminal charger", "#F5F5F5", d2 + 0.3, 62, "left"),
            (d1, 19.6, "+ depot plugs", "#FBFBFB", (d1 + 19.6) / 2, top - 2, "center")):
        ax.axvspan(x0, x1, color=c, zorder=0, lw=0)
        ax.text(tx, ty, lab, ha=ha, va="top", fontsize=6.8, color=MUTED)
    ax.plot([r["co2_t"] for r in nd], [(r["F1"] - f0) / 1e3 for r in nd],
            color="#7A7A7A", lw=1.0, zorder=2, label="Lower envelope")
    e = [r for r in pool if r["label"].startswith("eps_")]
    lp = [r for r in pool if r["label"].startswith(("lam_", "bp_lam_"))]
    ax.plot([r["co2_t"] for r in e], [(r["F1"] - f0) / 1e3 for r in e], "o",
            color=BLUE, ms=4.5, mec="white", mew=0.5, zorder=3, label="Emissions cap")
    ax.plot([r["co2_t"] for r in lp], [(r["F1"] - f0) / 1e3 for r in lp], "D",
            mfc="white", mec=ROSE, mew=1.1, ms=4.2, zorder=3, label="Carbon price")
    for lbl, txt, xy in (("econ_lam0", "D0", (17.2, 9)), ("eps_0.70", "D1", (9.6, 17)),
                         ("eps_0.20", "D2", (5.4, 34)), ("lam_5000", "D3", (3.3, 43)),
                         ("eps_0.00", "D4", (1.6, 66))):
        r = R[lbl]
        ax.annotate(txt, (r["co2_t"], (r["F1"] - f0) / 1e3), xytext=xy,
                    textcoords="data", fontsize=7, ha="left", va="center", bbox=BOX,
                    arrowprops=dict(arrowstyle="-", color="#8A8A8A", lw=0.6, shrinkB=3),
                    zorder=5)
    ax.text(10.4, 8.3, "about 0.7 kCAD/t", fontsize=6.8, color=INK, rotation=-8)
    ax.text(0.9, 47, "about\n44 kCAD/t", fontsize=6.8, color=INK, ha="left")
    ax.set_xlim(-0.6, 19.6)
    ax.set_ylim(-3, top)
    ax.set_xlabel("Onboard emissions (t CO$_2$/yr)")
    ax.set_ylabel("Cost over design D0 (kCAD/yr)")
    ax.legend(loc="center right", bbox_to_anchor=(1.0, 0.36))
    panel(ax, "a", x=-0.1)
    cats = ["Chargers and grid", "Electricity and demand charges",
            "Heater maintenance and diesel"]
    cols = [GREEN, "#9AA7B8", OCHRE]
    lbls = [("D0", "econ_lam0"), ("D1", "eps_0.70"), ("D2", "eps_0.20"),
            ("D3", "lam_5000"), ("D4", "eps_0.00")]
    vals = np.array([((R[l]["cost_parts"]["charger_site_capital"]
                       + R[l]["cost_parts"]["grid_capital"]) / 1e3,
                      (R[l]["cost_parts"]["demand_charges"]
                       + R[l]["cost_parts"]["electricity"]) / 1e3,
                      (R[l]["cost_parts"]["ffh_om"] + R[l]["cost_parts"]["diesel_cost"]) / 1e3)
                     for _, l in lbls])
    y = np.arange(len(lbls))
    left = np.zeros(len(lbls))
    d.grid(axis="y", visible=False)
    d.grid(axis="x", color=GRID, lw=0.6)
    for ci in range(3):
        d.barh(y, vals[:, ci], 0.6, left=left, color=cols[ci], edgecolor="white",
               lw=0.5, label=cats[ci])
        left += vals[:, ci]
    for yi, tot in zip(y, left):
        d.text(tot + 6, yi, f"{tot:,.0f}", va="center", fontsize=7)
    d.set_yticks(y, [n for n, _ in lbls])
    d.invert_yaxis()
    d.set_xlim(0, left.max() * 1.2)
    d.set_xlabel("Cost excluding buses (kCAD/yr)")
    d.legend(loc="upper center", bbox_to_anchor=(0.45, -0.2), ncols=1)
    panel(d, "b", x=-0.08)
    save(fig, "fig4_frontier")


# ------------------------------------------------------------- reliability
def fig_unc():
    series = [("econ_lam0", "D0, 18 heaters", BLUE, "o"),
              ("relmatch_eps0_r100#h", "Heater-free, 100 kWh reserve", GREEN, "^"),
              ("eps_0.00", "D4, heater-free", ROSE, "s"),
              ("det_designday#h", "Design-day, 3 heaters", OCHRE, "D")]
    x = np.arange(len(BANDS))
    fig, (a, b) = plt.subplots(1, 2, figsize=(W2, 6.4 * CM), sharey=True,
                               gridspec_kw={"wspace": 0.08})
    for ax, key, ttl in ((a, "p_reserve_compliant", "Days above the reserve"),
                         (b, "p_trips_completed", "Days with every trip completed")):
        for d, lab, c, mk in series:
            L = REL[f"{d}|data"]
            ax.plot(x, [100 * L[w][key] for w in BANDS], color=c, marker=mk, mfc=c,
                    mec="white", mew=0.6, label=lab)
        ax.set_xticks(x, BLBL)
        ax.set_title(ttl, fontsize=8, pad=4)
        ax.set_ylim(30, 102)
    a.set_ylabel("Share of sampled days (%)")
    a.legend(loc="lower left")
    panel(a, "a", x=-0.06)
    panel(b, "b", x=0.02)
    save(fig, "fig5_uncertainty")


# ------------------------------------------------------------- severe day
def fig_sevday():
    D = load("fig_severe_day_data.json")
    d0, d4 = D["designs"]["econ_lam0"], D["designs"]["eps_0.00"]
    fig, (a, b) = plt.subplots(1, 2, figsize=(W2, 6.0 * CM), gridspec_kw={"wspace": 0.26})
    a.plot(d0["soc_h"], d0["soc_kWh"], color=BLUE, lw=1.3, label="D0")
    a.plot(d4["soc_h"], d4["soc_kWh"], color=ROSE, lw=1.3, label="D4")
    a.axhline(d0["floor_kWh"], color=MUTED, lw=0.8, ls=(0, (2, 2)))
    a.text(min(d0["soc_h"]) + 0.2, d0["floor_kWh"] + 10, "State-of-charge floor",
           fontsize=6.8, color=MUTED)
    a.set_xlabel("Hour of day")
    a.set_ylabel("Battery energy (kWh)")
    a.legend(loc="upper right")
    panel(a, "a", x=-0.08)
    hrs = D["steps_h"]
    b.step(hrs, d0["depot_kW"], where="mid", color=BLUE, lw=1.2, label="D0 depot")
    b.step(hrs, d4["depot_kW"], where="mid", color=ROSE, lw=1.2, label="D4 depot")
    b.step(hrs, d4["terminal_kW"], where="mid", color=ROSE, lw=1.0, ls=(0, (3, 2)),
           label="D4 terminals")
    ticks = np.arange(6, 30, 4)
    b.set_xticks(ticks, [f"{int(h % 24):02d}" for h in ticks])
    b.set_xlabel("Hour (05:00 to 05:00 next day)")
    b.set_ylabel("Site load (kW)")
    b.set_ylim(0, 1000)
    b.legend(loc="upper left")
    panel(b, "b", x=-0.08)
    save(fig, "fig_severe_day")


# ------------------------------------------------------------- division
def _division_cases():
    D = load("campaign_division_v9rev.json")["cases"]
    A, C = D["A_fragmented"], D["C_shared_infra_frozen_z"]
    B = json.load(open("v10rev/div10_B.json"))["cases"]["B_shared_infra_route_locked"]
    lb = V10["division"]
    return D, A, B, C, lb


def fig_division():
    D, A, B, C, _ = _division_cases()
    Dn = json.load(open("v10rev/div10_D.json"))["cases"]["D_full_coordination"]
    Dv = D["D_full_coordination"]
    lb_joint = (Dn["differentiating_cost"] - Dn["abs_gap"]) / 1e3
    # full coordination: best solution of the two solves, bound of the later one
    Dbest = min((Dv, Dn), key=lambda c: c["differentiating_cost"])
    cases = [("Route by\nroute", A["lb_sum"] / 1e3, A["differentiating_cost"] / 1e3,
              A["n_ffh"], A["co2_t"], MUTED),
             ("Shared\nchargers", lb_joint, B["differentiating_cost"] / 1e3,
              B["n_ffh"], B["co2_t"], OCHRE),
             ("Shared\npool", lb_joint, C["differentiating_cost"] / 1e3,
              C["n_ffh"], C["co2_t"], BLUE),
             ("Full\ncoord.", lb_joint, Dbest["differentiating_cost"] / 1e3,
              Dbest["n_ffh"], Dbest["co2_t"], GREEN)]
    fig, (a, b, c) = plt.subplots(1, 3, figsize=(W2, 6.8 * CM),
                                  gridspec_kw={"width_ratios": [1.5, 1, 1], "wspace": 0.42})
    x = np.arange(4)
    for i, cs in enumerate(cases):
        a.vlines(i, cs[1], cs[2], color=cs[5], lw=5, alpha=0.35)
        a.plot([i - 0.16, i + 0.16], [cs[1], cs[1]], color=cs[5], lw=1.4)
        a.plot(i, cs[2], "o", color=cs[5], ms=5.5, mec="white", mew=0.6)
    a_lb, best = cases[0][1], min(cs[2] for cs in cases[1:])
    a.annotate("", xy=(0.5, best), xytext=(0.5, a_lb),
               arrowprops=dict(arrowstyle="<->", color=ROSE, lw=0.9))
    a.text(0.58, (a_lb + best) / 2, f"≥{a_lb - best:.0f}", color=ROSE, fontsize=7.5,
           va="center")
    a.set_xticks(x, [cs[0] for cs in cases])
    a.tick_params(axis="x", labelsize=6.8)
    a.set_xlim(-0.5, 3.5)
    a.set_ylim(3100, 3480)
    a.set_ylabel("Cost (kCAD/yr): lower bound to best solution")
    panel(a, "a", x=-0.12)
    for ax, k, lab, fmt in ((b, 3, "Heater-equipped buses", "{:.0f}"),
                            (c, 4, "Onboard emissions (t CO$_2$/yr)", "{:.0f}")):
        vals = [cs[k] for cs in cases]
        ax.bar(x, vals, 0.66, color=[cs[5] for cs in cases], edgecolor="white", lw=0.5)
        for i, v in enumerate(vals):
            ax.text(i, v * 1.02, fmt.format(v), ha="center", va="bottom", fontsize=7)
        ax.set_xticks(x, ["Route", "Chargers", "Pool", "Full"], rotation=30, ha="right")
        ax.tick_params(axis="x", labelsize=6.8)
        ax.set_ylabel(lab)
        ax.set_ylim(0, max(vals) * 1.18)
    panel(b, "b", x=-0.16)
    panel(c, "c", x=-0.16)
    save(fig, "fig_division")


# ------------------------------------------------------------- routes
def fig_routes():
    dv = load("campaign_division_v9rev.json")["cases"]
    per = dv["A_fragmented"]["per_route"]
    C = dv["C_shared_infra_frozen_z"]
    routes = sorted(per, key=lambda r: (per[r]["n_ffh"] / max(1, per[r]["n_buses"]),
                                        per[r]["n_buses"]))
    share = [100 * per[r]["n_ffh"] / max(1, per[r]["n_buses"]) for r in routes]
    pool = 100 * C["n_ffh"] / C["n_buses"]
    fig, ax = plt.subplots(figsize=(W1, 7.8 * CM))
    y = np.arange(len(routes))
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=GRID, lw=0.6)
    ax.barh(y, share, 0.66, color=[INK if r == "52" else OCHRE for r in routes],
            edgecolor="white", lw=0.5)
    for yi, r, s in zip(y, routes, share):
        ax.text(s + 1.2, yi, f"{per[r]['n_ffh']} of {per[r]['n_buses']}", va="center",
                fontsize=6.8, color=MUTED)
    ax.axvline(pool, color=BLUE, lw=1.2, ls=(0, (3, 2)))
    ax.text(pool + 1.2, len(routes) - 0.2, f"Shared bus pool: {C['n_ffh']} of "
            f"{C['n_buses']} ({pool:.0f}%)", fontsize=7, color=BLUE, va="bottom")
    ax.set_yticks(y, [f"Route {r}" for r in routes])
    ax.set_ylim(-0.6, len(routes) + 0.5)
    ax.set_xlabel("Heater-equipped buses when the route is planned alone (%)")
    ax.set_xlim(0, 118)
    ax.set_xticks([0, 25, 50, 75, 100])
    save(fig, "figS_routes")


if __name__ == "__main__":
    for f in (fig_robust, fig_frontier, fig_unc, fig_sevday, fig_division, fig_routes):
        f()
