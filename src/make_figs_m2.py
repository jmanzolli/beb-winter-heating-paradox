"""
Figures of the long-format manuscript (main_2.tex, single-column Elsevier CAS
layout) in one house style: "clean sans" (Helvetica, open axes, light
horizontal grid) with framed legends and label boxes.

Every figure is drawn at its print size (12.5 cm, or 16.5 cm for full-width
figures; the text width of the layout is 16.5 cm) and included without
scaling, so the type prints at its nominal size (8 pt; 7.5 pt for ticks and
legends). The categorical palette passes the dataviz palette validator
(colour-blind separation, lightness, chroma, contrast) on a white surface;
ordered categories (weather bands) use a single-hue sequential ramp.

The IEEE figures (make_fig_m.py, make_figs_v9extra.py) are unchanged; these
are written to ../overleaf-git/figures/m2/.

Usage (from code/):
    python3 make_figs_m2.py [data dir, default v9rev]
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

DATA = sys.argv[1] if len(sys.argv) > 1 else "v9rev"
OUT = "../overleaf-git/figures/m2"
os.makedirs(OUT, exist_ok=True)
os.makedirs("ieee_figs/m2", exist_ok=True)

CM = 1 / 2.54
W1, W2 = 12.5 * CM, 16.5 * CM

# categorical palette (validated, fixed order): blue, green, rose, ochre
BLUE, GREEN, ROSE, OCHRE = "#3F6FB5", "#2E9443", "#E06377", "#B58A1B"
INK, MUTED, GRID = "#222222", "#6B6B6B", "#E3E3E3"
# sequential single-hue ramp for the ordered weather bands (light -> dark)
RAMP = ["#D6E2F3", "#A9C1E6", "#7598D2", "#3F6FB5", "#1E3F75"]

plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["Helvetica", "Arial"],
    "mathtext.fontset": "custom", "mathtext.rm": "Helvetica",
    "mathtext.it": "Helvetica:italic", "mathtext.bf": "Helvetica:bold",
    "font.size": 8, "axes.labelsize": 8, "axes.titlesize": 8,
    "xtick.labelsize": 7.5, "ytick.labelsize": 7.5, "legend.fontsize": 7.5,
    "text.color": INK, "axes.labelcolor": INK, "xtick.color": INK, "ytick.color": INK,
    "axes.edgecolor": "#444444", "axes.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False,
    "xtick.direction": "out", "ytick.direction": "out",
    "xtick.major.size": 2.5, "ytick.major.size": 2.5,
    "xtick.major.width": 0.6, "ytick.major.width": 0.6,
    "axes.grid": True, "axes.grid.axis": "y", "grid.color": GRID,
    "grid.linewidth": 0.6, "axes.axisbelow": True,
    # framed legends (user's choice): thin grey frame, opaque white fill
    "legend.frameon": True, "legend.fancybox": False, "legend.framealpha": 1.0,
    "legend.edgecolor": "#9A9A9A", "legend.facecolor": "white",
    "legend.borderpad": 0.45, "legend.handlelength": 1.6,
    "legend.columnspacing": 1.1, "legend.handletextpad": 0.5,
    "patch.linewidth": 0.6,
    "lines.linewidth": 1.5, "lines.markersize": 4.5,
    "pdf.fonttype": 42, "savefig.dpi": 300,
})
BOX = dict(boxstyle="square,pad=0.3", fc="white", ec="#9A9A9A", lw=0.6)

BANDS = ["mild", "cold", "verycold", "extreme", "severe"]
BLBL = ["Mild", "Cold", "Very cold", "Extreme", "Severe"]


def load(fn):
    return json.load(open(os.path.join(DATA, fn)))


def runs(fn):
    return {r["label"]: r for r in load(fn)["runs"] if "F1" in r}


def panel(ax, s, x=-0.01, y=1.02):
    ax.text(x, y, f"({s})", transform=ax.transAxes, fontsize=8.5,
            fontweight="bold", ha="right", va="bottom")


def save(fig, name):
    fig.savefig(f"{OUT}/{name}.pdf", bbox_inches="tight", pad_inches=0.03)
    fig.savefig(f"ieee_figs/m2/{name}.png", bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)
    print("wrote", name)


R = runs("campaign_v9rev_results.json")
RES = load("campaign_v9rev_results.json")


# ------------------------------------------------------------- weather
def fig_weather():
    wea = json.load(open(os.environ.get("M2_WEATHER", "data_v9/eccc_winter_bands_v9.json")))["winters"]
    yrs = list(wea)
    cnt = {b: np.array([wea[y][b] * 151.0 / wea[y]["n"] for y in yrs]) for b in BANDS}
    fig, ax = plt.subplots(figsize=(W2, 5.6 * CM))
    x = np.arange(len(yrs))
    bottom = np.zeros(len(yrs))
    for b, lab, col in zip(reversed(BANDS), reversed(BLBL), reversed(RAMP)):
        ax.bar(x, cnt[b], 0.78, bottom=bottom, color=col, edgecolor="white",
               linewidth=0.5, label=lab)
        bottom += cnt[b]
    ax.set_xlim(-0.6, len(yrs) - 0.4)
    ax.set_ylim(0, 151)
    ax.set_yticks([0, 50, 100, 150])
    ax.set_xticks(x[::2], [f"{y[:4]}–{y[5:]}" for y in yrs][::2], rotation=0)
    ax.tick_params(axis="x", labelsize=7)
    ax.set_ylabel("Days per winter")
    h, l = ax.get_legend_handles_labels()
    ax.legend(h[::-1], l[::-1], ncols=5, loc="upper center",
              bbox_to_anchor=(0.5, 1.16))
    save(fig, "fig_weather")


# ------------------------------------------------------------- operation (D0)
def fig_ops():
    so = R["econ_lam0"]["scen_ops"]
    x = np.arange(len(BANDS))
    pre = np.array([so[w]["precond_kWh"] for w in BANDS])
    qel = np.array([so[w]["q_el_kWh"] for w in BANDS])
    qff = np.array([so[w]["q_ffh_kWh"] for w in BANDS])
    dsl = np.array([so[w]["diesel_L"] for w in BANDS])
    xt = [f"{l}\n{so[w]['T']:+.1f}°C" for l, w in zip(BLBL, BANDS)]
    fig, (a, b) = plt.subplots(2, 1, figsize=(W1, 8.2 * CM), sharex=True,
                               gridspec_kw={"height_ratios": [1.7, 1], "hspace": 0.18})
    a.bar(x, pre, 0.62, color="#9AA7B8", edgecolor="white", lw=0.6, label="Preconditioning")
    a.bar(x, qel, 0.62, bottom=pre, color=BLUE, edgecolor="white", lw=0.6, label="Electric heater")
    a.bar(x, qff, 0.62, bottom=pre + qel, color=OCHRE, edgecolor="white", lw=0.6, label="FFH")
    tot = pre + qel + qff
    for i in range(len(BANDS)):
        if qff[i] / tot[i] > 0.03:
            a.text(i, tot[i] + 60, f"FFH {100 * qff[i] / tot[i]:.0f}%", ha="center",
                   va="bottom", fontsize=7, color=INK)
    a.set_ylabel("Cabin heat (kWh/day)")
    a.set_ylim(0, tot.max() * 1.18)
    a.legend(loc="upper left", ncols=3)
    panel(a, "a")
    b.bar(x, dsl, 0.62, color=OCHRE, edgecolor="white", lw=0.6)
    for i, v in enumerate(dsl):
        if v > 5:
            b.text(i, v + 12, f"{v:.0f}", ha="center", va="bottom", fontsize=7)
    b.set_ylabel("Diesel (L/day)")
    b.set_ylim(0, dsl.max() * 1.25)
    b.set_xticks(x, xt)
    panel(b, "b")
    save(fig, "fig3_ops")


# ------------------------------------------------------------- depot load and price
def fig_price():
    D = load("figdata_price_v9.json")
    hrs = np.array(D["hours"])
    clock = np.where(hrs < D["t0_h"] - 1e-9, hrs + 24, hrs)
    fig, (a, b) = plt.subplots(2, 1, figsize=(W1, 7.6 * CM), sharex=True,
                               gridspec_kw={"height_ratios": [2.2, 1], "hspace": 0.22})
    des = D["designs"]
    for lb, w, col, ls, lab in (("econ_lam0", "mild", BLUE, (0, (3, 2)), "D0, mild day"),
                                ("econ_lam0", "severe", BLUE, "-", "D0, severe day"),
                                ("eps_0.00", "severe", ROSE, "-", "D4, severe day")):
        a.step(clock, np.array(des[lb]["scen"][w]["depot_kW"]), where="mid",
               color=col, ls=ls, lw=1.3, label=lab)
    a.set_ylabel("Depot load (kW)")
    a.set_ylim(0, 1150)
    a.legend(loc="upper left", ncols=3)
    panel(a, "a")
    b.step(clock, np.array(D["price"]["mild"]) * 100, where="mid", color=MUTED, lw=1.1)
    b.set_ylabel("Price (¢/kWh)")
    b.set_ylim(9.5, 15)
    ticks = np.arange(6, 30, 3)
    b.set_xticks(ticks, [f"{int(t % 24):02d}:00" for t in ticks])
    b.set_xlabel("Hour of day (05:00 to 05:00 next day)")
    b.set_xlim(clock.min(), clock.max())
    panel(b, "b")
    save(fig, "fig_price")


# ------------------------------------------------------------- robustness
VARIANTS = [
    ("Base case", None),
    ("Useful-heat fraction 0.55", "addon_phi055_v9.json"),
    ("Useful-heat fraction 0.60", "addon_phi060_v9.json"),
    ("Cabin heat −6%", "addon_heat094_v9.json"),
    ("Cabin heat +3.5%", "addon_heat1035_v9.json"),
    ("Burner fuel rate 70%", "addon_fuel070_v9.json"),
    ("Burner fuel rate 115%", "addon_fuel115_v9.json"),
    ("Severe traction 1.15", "sev115_v9.json"),
    ("Severe traction 1.30", "sev130_v9.json"),
    ("Min. plug session 30 min", "addon_plug30_v9.json"),
    ("Min. plug session 60 min", "addon_plug60_v9.json"),
    ("Battery wear 0.07 CAD/kWh", "addon_wear_v9.json"),
    ("Daily-minimum weights", "addon_coldw_v9.json"),
    ("Heat-pump cabin heating", "addon_hp_v9.json"),
]


def fig_robust():
    rows = []
    for lab, fn in VARIANTS:
        rr = runs("campaign_v9_results.json") if fn is None else runs(fn)
        e, z = rr["econ_lam0"], rr["eps_0.00"]
        rows.append((lab, e["co2_t"], e["n_ffh"], 100 * (z["F1"] - e["F1"]) / e["F1"]))
    n = len(rows)
    y = np.arange(n)[::-1]
    fig, (a, b) = plt.subplots(1, 2, figsize=(W2, 7.4 * CM), sharey=True,
                               gridspec_kw={"wspace": 0.06})
    for ax in (a, b):
        ax.grid(axis="y", visible=False)
        ax.grid(axis="x", color=GRID, lw=0.6)
    co2 = np.array([r[1] for r in rows])
    prem = np.array([r[3] for r in rows])
    cols = [ROSE] + [BLUE] * (n - 1)
    a.hlines(y, 0, co2, color="#C8D3E6", lw=1.0)
    a.scatter(co2, y, s=22, color=cols, zorder=3, edgecolor="white", linewidth=0.6)
    for yi, r in zip(y, rows):
        a.text(r[1] + 0.9, yi, f"{r[2]} FFH", va="center", fontsize=6.8, color=MUTED)
    a.axvline(co2[0], color=ROSE, lw=0.7, ls=(0, (2, 2)))
    a.set_xlim(0, co2.max() * 1.28)
    a.set_xlabel("Baseline onboard emissions (t CO$_2$/yr)")
    a.set_yticks(y, [r[0] for r in rows])
    panel(a, "a")
    b.hlines(y, 0, prem, color="#C8D3E6", lw=1.0)
    b.scatter(prem, y, s=22, color=cols, zorder=3, edgecolor="white", linewidth=0.6)
    b.axvline(prem[0], color=ROSE, lw=0.7, ls=(0, (2, 2)))
    b.set_xlim(0, prem.max() * 1.15)
    b.set_xlabel("FFH-free premium (% of fleet cost)")
    panel(b, "b")
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
    fig, ax = plt.subplots(figsize=(W1, 7.0 * CM))
    d1, d2 = R["eps_0.70"]["co2_t"], R["eps_0.20"]["co2_t"]
    top = 78
    for x0, x1, lab, c in ((-0.6, d2, "Terminal charging", "#F1F1F1"),
                           (d2, d1, "Mixed fleet", "#F7F7F7"),
                           (d1, 19.6, "Depot charging", "#FBFBFB")):
        ax.axvspan(x0, x1, color=c, zorder=0, lw=0)
        ax.text((x0 + x1) / 2, top - 2, lab, ha="center", va="top", fontsize=7, color=MUTED)
    ax.plot([r["co2_t"] for r in nd], [(r["F1"] - f0) / 1e3 for r in nd],
            color="#7A7A7A", lw=1.0, zorder=2, label="Lower envelope")
    e = [r for r in pool if r["label"].startswith("eps_")]
    lp = [r for r in pool if r["label"].startswith(("lam_", "bp_lam_"))]
    ax.plot([r["co2_t"] for r in e], [(r["F1"] - f0) / 1e3 for r in e], "o",
            color=BLUE, ms=4.5, mec="white", mew=0.5, zorder=3, label="Emissions cap")
    ax.plot([r["co2_t"] for r in lp], [(r["F1"] - f0) / 1e3 for r in lp], "D",
            mfc="white", mec=ROSE, mew=1.1, ms=4.2, zorder=3, label="Carbon price")
    for lbl, txt, xy in (("econ_lam0", "D0 Economic baseline", (15.3, 12)),
                         ("eps_0.70", "D1 Depot charger\nreconfiguration", (9.4, 21)),
                         ("eps_0.20", "D2 Mixed fleet", (5.2, 37)),
                         ("lam_5000", "D3 Terminal charger\nupgrade", (2.4, 49)),
                         ("eps_0.00", "D4 Full heating\nelectrification", (1.2, 64))):
        r = R[lbl]
        ax.annotate(txt, (r["co2_t"], (r["F1"] - f0) / 1e3), xytext=xy,
                    textcoords="data", fontsize=7, ha="left", va="center", bbox=BOX,
                    arrowprops=dict(arrowstyle="-", color="#8A8A8A", lw=0.6, shrinkB=3),
                    zorder=5)
    ax.set_xlim(-0.6, 19.6)
    ax.set_ylim(-3, top)
    ax.set_xlabel("Onboard emissions (t CO$_2$/yr)")
    ax.set_ylabel("Cost increment over D0 (kCAD/yr)")
    ax.legend(loc="center right", bbox_to_anchor=(1.0, 0.42))
    save(fig, "fig4_frontier")


# ------------------------------------------------------------- reliability
def fig_unc():
    A = load("rel_v9rev_econ_full.json")["levels"]
    Z = load("rel_v9rev_zero_full.json")["levels"]
    x = np.arange(len(BANDS))
    fig, ax = plt.subplots(figsize=(W1, 6.4 * CM))
    for L, c, lab, ls, mk in ((A["heat_cv_0.00"], BLUE, "D0, traction draws", "-", "o"),
                              (Z["heat_cv_0.00"], ROSE, "D4, traction draws", "-", "s"),
                              (A["heat_cv_0.20"], BLUE, "D0, + cabin-heat CV 0.20", (0, (3, 2)), "o"),
                              (Z["heat_cv_0.20"], ROSE, "D4, + cabin-heat CV 0.20", (0, (3, 2)), "s")):
        solid = ls == "-"
        ax.plot(x, [100 * L[w]["p_all_trips_served"] for w in BANDS], ls=ls, color=c,
                marker=mk, mfc=c if solid else "white", mec=c, mew=1.1, label=lab)
    ax.set_xticks(x, BLBL)
    ax.set_ylabel("Days fully served (%)")
    ax.set_ylim(0, 104)
    ax.legend(loc="lower left", ncols=2)
    save(fig, "fig5_uncertainty")


# ------------------------------------------------------------- severe day
def fig_sevday():
    D = load("fig_severe_day_data.json")
    d0, d4 = D["designs"]["econ_lam0"], D["designs"]["eps_0.00"]
    fig, axes = plt.subplots(2, 2, figsize=(W2, 11.0 * CM),
                             gridspec_kw={"hspace": 0.62, "wspace": 0.26})
    (a, b), (c, d) = axes
    a.plot(d0["soc_h"], d0["soc_kWh"], color=BLUE, lw=1.3, label="D0")
    a.plot(d4["soc_h"], d4["soc_kWh"], color=ROSE, lw=1.3, label="D4")
    a.axhline(d0["floor_kWh"], color=MUTED, lw=0.8, ls=(0, (2, 2)))
    a.text(min(d0["soc_h"]) + 0.2, d0["floor_kWh"] + 10, "State-of-charge floor",
           fontsize=6.8, color=MUTED)
    a.set_xlabel("Hour of day")
    a.set_ylabel("Battery energy (kWh)")
    a.legend(loc="upper right")
    panel(a, "a")
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
    panel(b, "b")
    x = np.arange(len(BANDS))
    wd = 0.36
    e0 = np.array([d0["heat_kWh"][w]["electric"] for w in BANDS])
    f0 = np.array([d0["heat_kWh"][w]["ffh"] for w in BANDS])
    e4 = np.array([d4["heat_kWh"][w]["electric"] for w in BANDS])
    c.bar(x - wd / 2 - 0.01, e0, wd, color=BLUE, edgecolor="white", lw=0.5,
          label="D0 electric heater (left bar)")
    c.bar(x - wd / 2 - 0.01, f0, wd, bottom=e0, color=OCHRE, edgecolor="white", lw=0.5,
          label="D0 FFH (left bar)")
    c.bar(x + wd / 2 + 0.01, e4, wd, color="#9DB4DA", edgecolor="white", lw=0.5,
          label="D4 electric heater (right bar)")
    c.set_xticks(x, ["Mild", "Cold", "Very\ncold", "Extreme", "Severe"])
    c.set_ylabel("Cabin heat (kWh/day)")
    c.set_ylim(0, max((e0 + f0).max(), e4.max()) * 1.12)
    c.legend(loc="upper center", bbox_to_anchor=(0.5, -0.32), ncols=1)
    panel(c, "c")
    cats = ["Chargers and grid", "Electricity and demand charges", "FFH maintenance and diesel"]
    cols = [GREEN, "#9AA7B8", OCHRE]
    lbls = [("D0", "econ_lam0"), ("D1", "eps_0.70"), ("D2", "eps_0.20"),
            ("D3", "lam_5000"), ("D4", "eps_0.00")]
    vals = []
    for _, l in lbls:
        cp = R[l]["cost_parts"]
        vals.append(((cp["charger_site_capital"] + cp["grid_capital"]) / 1e3,
                     (cp["demand_charges"] + cp["electricity"]) / 1e3,
                     (cp["ffh_om"] + cp["diesel_cost"]) / 1e3))
    vals = np.array(vals)
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
    d.set_xlim(0, left.max() * 1.16)
    d.set_xlabel("Annual cost excluding buses (kCAD/yr)")
    d.legend(loc="upper center", bbox_to_anchor=(0.45, -0.32), ncols=1)
    panel(d, "d")
    save(fig, "fig_severe_day")


# ------------------------------------------------------------- division
def fig_division():
    D = load("campaign_division_v9rev.json")["cases"]
    A = D["A_fragmented"]
    a_inc = A["differentiating_cost"] / 1e3
    a_lb = A["lb_sum"] / 1e3
    a_cb = A["common_basis"]["differentiating_cost"] / 1e3
    C, Dd = D["C_shared_infra_frozen_z"], D["D_full_coordination"]
    cases = [("Fragmented", a_lb, a_inc, A["n_ffh"], A["common_basis"]["coincident_peak_kW"]["win"] / 1e3, MUTED),
             ("Shared pool", (C["differentiating_cost"] - C["abs_gap"]) / 1e3,
              C["differentiating_cost"] / 1e3, C["n_ffh"], C["peak_depot_kW"] / 1e3, BLUE),
             ("Full coordination", (Dd["differentiating_cost"] - Dd["abs_gap"]) / 1e3,
              Dd["differentiating_cost"] / 1e3, Dd["n_ffh"], Dd["peak_depot_kW"] / 1e3, GREEN)]
    fig, (a, b, c) = plt.subplots(1, 3, figsize=(W2, 6.6 * CM),
                                  gridspec_kw={"width_ratios": [1.5, 1, 1], "wspace": 0.42})
    x = np.arange(3)
    for i, cs in enumerate(cases):
        a.vlines(i, cs[1], cs[2], color=cs[5], lw=5, alpha=0.35)
        a.plot([i - 0.14, i + 0.14], [cs[1], cs[1]], color=cs[5], lw=1.4)
        a.plot(i, cs[2], "o", color=cs[5], ms=5.5, mec="white", mew=0.6)
    a.plot(0, a_cb, "s", mfc="white", mec=MUTED, mew=1.1, ms=5.5)
    a.annotate("re-billed on one\nconnection", (0, a_cb), xytext=(0.32, a_cb - 25),
               fontsize=6.8, va="center", bbox=BOX,
               arrowprops=dict(arrowstyle="-", color="#8A8A8A", lw=0.6))
    best = min(cs[2] for cs in cases[1:])
    a.annotate("", xy=(0.55, best), xytext=(0.55, a_lb),
               arrowprops=dict(arrowstyle="<->", color=ROSE, lw=0.9))
    a.text(0.62, (a_lb + best) / 2, f"≥{a_lb - best:.0f}", color=ROSE,
           fontsize=7.5, va="center")
    a.set_xticks(x, ["Frag.", "Pool", "Coord."])
    a.set_xlim(-0.5, 2.5)
    a.set_ylim(3050, a_cb + 60)
    a.set_ylabel("Cost (kCAD/yr)")
    panel(a, "a")
    for ax, k, lab, fmt in ((b, 3, "FFH-equipped buses", "{:.0f}"),
                            (c, 4, "Depot peak (MW)", "{:.1f}")):
        vals = [cs[k] for cs in cases]
        ax.bar(x, vals, 0.62, color=[cs[5] for cs in cases], edgecolor="white", lw=0.5)
        for i, v in enumerate(vals):
            ax.text(i, v * 1.02, fmt.format(v), ha="center", va="bottom", fontsize=7)
        ax.set_xticks(x, ["Frag.", "Pool", "Coord."])
        ax.set_ylabel(lab)
        ax.set_ylim(0, max(vals) * 1.18)
    panel(b, "b")
    panel(c, "c")
    save(fig, "fig_division")


# ------------------------------------------------------------- routes
def fig_routes():
    dv = load("campaign_division_v9rev.json")["cases"]
    per = dv["A_fragmented"]["per_route"]
    Dc = min((c for k, c in dv.items() if k != "A_fragmented" and c.get("differentiating_cost")),
             key=lambda c: c["differentiating_cost"])
    routes = sorted(per, key=lambda r: per[r]["n_ffh"] / max(1, per[r]["n_buses"]))
    share = [100 * per[r]["n_ffh"] / max(1, per[r]["n_buses"]) for r in routes]
    coord = 100 * Dc["n_ffh"] / Dc["n_buses"]
    fig, ax = plt.subplots(figsize=(W1, 7.6 * CM))
    y = np.arange(len(routes))
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=GRID, lw=0.6)
    ax.barh(y, share, 0.66, color=OCHRE, edgecolor="white", lw=0.5,
            label="Route planned alone")
    ax.axvline(coord, color=BLUE, lw=1.2, ls=(0, (3, 2)),
               label=f"Coordinated fleet ({coord:.0f}%)")
    ax.set_yticks(y, [f"Route {r} ({per[r]['n_buses']} buses)" for r in routes])
    ax.set_xlabel("Share of FFH-equipped buses (%)")
    ax.set_xlim(0, 105)
    ax.legend(loc="lower right")
    save(fig, "figS_routes")


if __name__ == "__main__":
    for f in (fig_weather, fig_ops, fig_price, fig_robust, fig_frontier, fig_unc,
              fig_sevday, fig_division, fig_routes):
        f()
