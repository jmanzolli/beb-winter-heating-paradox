"""
Four v9 figures for the main paper (same visual identity as make_fig_m.py):

  fig_weather.pdf   days per temperature band in each of the 24 winters
                    (ECCC Toronto City daily means) and the planning weights
  fig_price.pdf     (a) hourly energy price, winter and off-season
                    (b) depot load on a mild and a severe day, economic
                        baseline vs FFH-free design (fixed-design re-solve)
  fig_robust.pdf    economic baseline and FFH-free premium across the
                    companion-study ranges and the v9 add-on variants
  fig_division.pdf  fragmented vs coordinated division planning: certified
                    cost intervals, FFH-equipped buses, depot peak

Inputs (env, defaults in brackets):
  V9_DIR     directory with the v9 result files            [v9_partial]
  V9_INPUTS  Route 52 inputs file                          [route52_inputs_v9.json]
  V9_WEATHER per-winter band counts                        [data_v9/eccc_winter_bands_v9.json]
Outputs: ieee_figs/ and ../overleaf-git/figures/
"""
import json
import os
import shutil

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

BLUE, TEAL, ORANGE = "#1F4E79", "#2E8B8B", "#C55A11"
GRAY, LGRAY = "#7F7F7F", "#C9C9C9"
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "pdf.fonttype": 42, "ps.fonttype": 42,
    "font.size": 8, "axes.labelsize": 8.5, "xtick.labelsize": 8,
    "ytick.labelsize": 8, "legend.fontsize": 7.5,
    "axes.linewidth": 0.6, "xtick.major.width": 0.6, "ytick.major.width": 0.6,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "axes.grid.axis": "y", "grid.color": "#DDDDDD",
    "grid.linewidth": 0.4, "axes.axisbelow": True,
    "legend.frameon": False, "figure.facecolor": "white",
    "axes.facecolor": "white", "savefig.facecolor": "white",
})
COLW = 3.5  # IEEE column width [in]

V9 = os.environ.get("V9_DIR", "v9_partial")
INP = json.load(open(os.environ.get("V9_INPUTS", "route52_inputs_v9.json")))
WEA = json.load(open(os.environ.get("V9_WEATHER",
                                    "data_v9/eccc_winter_bands_v9.json")))
OUT = "ieee_figs"
os.makedirs(OUT, exist_ok=True)
FIGDIRS = [d for d in ("../overleaf-git/figures",) if os.path.isdir(d)]

BANDS = ["mild", "cold", "verycold", "extreme", "severe"]
BAND_LBL = {"mild": "Mild ($\\geq$0$^\\circ$C)", "cold": "Cold (-5 to 0)",
            "verycold": "Very cold (-10 to -5)",
            "extreme": "Extreme (-15 to -10)", "severe": "Severe (<-15)"}
BAND_SHORT = {"mild": "Mild", "cold": "Cold", "verycold": "Very cold",
              "extreme": "Extreme", "severe": "Severe"}
BAND_COL = {"mild": "#DCE6F0", "cold": "#9DB9D5", "verycold": "#4F7FAF",
            "extreme": BLUE, "severe": ORANGE}


def save(fig, name):
    fig.savefig(f"{OUT}/{name}.pdf", bbox_inches="tight", pad_inches=0.02)
    fig.savefig(f"{OUT}/{name}.png", dpi=300, bbox_inches="tight",
                pad_inches=0.02)
    plt.close(fig)
    for d in FIGDIRS:
        shutil.copy(f"{OUT}/{name}.pdf", f"{d}/{name}.pdf")
    print("wrote", name)


def runs(fn):
    return {r["label"]: r for r in json.load(open(f"{V9}/{fn}"))["runs"]
            if "F1" in r}


# ---------------------------------------------------------------- weather
def fig_weather():
    W = WEA["winters"]
    yrs = list(W)
    # each winter scaled to 151 days, as for the planning weights
    cnt = {b: np.array([W[y][b] * 151.0 / W[y]["n"] for y in yrs])
           for b in BANDS}
    fig, ax = plt.subplots(figsize=(COLW, 1.45))
    x = np.arange(len(yrs))
    # stack from the coldest band up so cold-day variation is readable
    bottom = np.zeros(len(yrs))
    for b in reversed(BANDS):
        ax.bar(x, cnt[b], 0.78, bottom=bottom, color=BAND_COL[b],
               edgecolor="white", linewidth=0.3, label=BAND_SHORT[b])
        bottom += cnt[b]
    cold = cnt["extreme"] + cnt["severe"]
    mean_cold = cold.mean()
    ax.set_xlim(-0.6, len(yrs) - 0.4)
    ax.set_ylim(0, 151)
    ax.set_yticks([0, 50, 100, 150])
    ax.set_xticks(x[::4], [f"{y[:4]}\u2013{y[5:]}" for y in yrs][::4], fontsize=7)
    ax.set_ylabel("Days")
    h, l = ax.get_legend_handles_labels()
    ax.legend(h[::-1], l[::-1], ncol=5, loc="lower center",
              bbox_to_anchor=(0.5, 1.0), fontsize=6.4, handlelength=0.9,
              columnspacing=0.7, handletextpad=0.3)
    print(f"  extreme+severe days per winter: mean {mean_cold:.1f}, "
          f"range {cold.min():.0f}-{cold.max():.0f}")
    save(fig, "fig_weather")


# ---------------------------------------------------------------- price
def fig_price():
    fn = f"{V9}/figdata_price_v9.json"
    if not os.path.exists(fn):
        print("skip fig_price: no", fn)
        return
    D = json.load(open(fn))
    hrs = np.array(D["hours"])
    # continuous service-day clock: 05:00 ... 29:00 (next morning)
    clock = np.where(hrs < D["t0_h"] - 1e-9, hrs + 24, hrs)
    fig, b = plt.subplots(figsize=(COLW, 1.75))
    pw = np.array(D["price"]["mild"]) * 100
    a = b.twinx()
    a.step(clock, pw, where="mid", color=GRAY, lw=0.8, ls="--")
    a.set_ylabel("Winter price [\u00a2/kWh]", color=GRAY, fontsize=7.5)
    a.tick_params(axis="y", colors=GRAY, labelsize=7)
    a.spines["right"].set_visible(True)
    a.spines["right"].set_color(GRAY)
    a.grid(False)
    a.set_ylim(2, 22)
    a.set_yticks([10, 12, 14])
    des = D["designs"]
    sty = [("econ_lam0", "severe", BLUE, "-", "Baseline, severe"),
           ("econ_lam0", "mild", BLUE, ":", "Baseline, mild"),
           ("eps_0.00", "severe", ORANGE, "-", "FFH-free, severe")]
    for lb, w, col, ls, lab in sty:
        if lb not in des:
            continue
        y = np.array(des[lb]["scen"][w]["depot_kW"])
        b.plot(clock, y, ls, color=col, lw=1.0, label=lab)
    b.plot([], [], "--", color=GRAY, lw=0.8, label="Price (right)")
    b.set_ylabel("Depot load [kW]")
    ticks = np.arange(6, 30, 3)
    b.set_xticks(ticks, [f"{int(t % 24):02d}" for t in ticks])
    b.set_xlabel("Hour (05:00 to 05:00 next day)")
    b.set_xlim(clock.min(), clock.max())
    b.set_ylim(0, 1300)
    b.legend(loc="upper left", fontsize=6.4, ncol=2, columnspacing=0.8,
             handlelength=1.4)
    # where the energy goes: share of depot energy in the cheapest 6 hours
    for lb in des:
        for w in ("mild", "severe"):
            y = np.array(des[lb]["scen"][w]["depot_kW"])
            p = np.array(D["price"][w])
            cheap = p <= np.sort(np.unique(p))[min(5, len(np.unique(p)) - 1)]
            print(f"  {lb} {w}: depot {y.sum() * D['dt_h']:.0f} kWh, peak "
                  f"{y.max():.0f} kW, mean price "
                  f"{(y * p).sum() / max(y.sum(), 1e-9) * 100:.2f} c/kWh, "
                  f"share in cheapest hours {y[cheap].sum() / max(y.sum(), 1e-9):.2f}")
    save(fig, "fig_price")


# ---------------------------------------------------------------- robustness
VARIANTS = [
    ("Base case", None),
    ("Useful-heat fraction 0.55", "addon_phi055_v9.json"),
    ("Useful-heat fraction 0.60", "addon_phi060_v9.json"),
    ("Cabin heat $-$6%", "addon_heat094_v9.json"),
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
    base = runs("campaign_v9_results.json")
    rows = []
    for lab, fn in VARIANTS:
        R = base if fn is None else runs(fn)
        e, z = R.get("econ_lam0"), R.get("eps_0.00")
        if not e or not z:
            print("  missing", lab)
            continue
        rows.append((lab, e["co2_t"], e["n_ffh"],
                     100 * (z["F1"] - e["F1"]) / e["F1"]))
    n = len(rows)
    y = np.arange(n)[::-1]
    fig, (a, b) = plt.subplots(1, 2, figsize=(COLW, 2.2), sharey=True,
                               gridspec_kw={"width_ratios": [1, 1],
                                            "wspace": 0.08})
    for ax in (a, b):
        ax.grid(axis="x", color="#DDDDDD", lw=0.4)
        ax.grid(axis="y", visible=False)
        for i in range(n):
            if i % 2 == 0:
                ax.axhspan(y[i] - 0.5, y[i] + 0.5, color="#F4F4F4", lw=0,
                           zorder=0)
    co2 = np.array([r[1] for r in rows])
    prem = np.array([r[3] for r in rows])
    cols = [ORANGE if i == 0 else BLUE for i in range(n)]
    a.hlines(y, 0, co2, color=LGRAY, lw=0.8)
    a.scatter(co2, y, s=16, color=cols, zorder=3)
    for yi, r in zip(y, rows):
        a.text(r[1] + 0.8, yi, f"{r[2]}", va="center", fontsize=6.3,
               color=GRAY)
    a.axvline(co2[0], color=ORANGE, lw=0.6, ls=":")
    a.set_xlim(0, max(co2) * 1.22)
    a.set_xlabel("Baseline CO$_2$ [t/yr]")
    a.set_yticks(y, [r[0] for r in rows], fontsize=6.4)
    a.text(0.0, 1.02, "(a)", transform=a.transAxes, fontweight="bold",
           fontsize=8.5)
    a.text(1.0, 1.02, "labels: FFH buses", transform=a.transAxes, ha="right",
           fontsize=6, color=GRAY)
    b.hlines(y, 0, prem, color=LGRAY, lw=0.8)
    b.scatter(prem, y, s=16, color=cols, zorder=3)
    b.axvline(prem[0], color=ORANGE, lw=0.6, ls=":")
    b.set_xlim(0, max(prem) * 1.15)
    b.set_xlabel("FFH-free premium [%]")
    b.text(0.0, 1.02, "(b)", transform=b.transAxes, fontweight="bold",
           fontsize=8.5)
    a.set_ylim(-0.6, n - 0.4)
    for r in rows:
        print(f"  {r[0]:28s} co2 {r[1]:6.2f} ffh {r[2]:2d} premium {r[3]:.2f}%")
    save(fig, "fig_robust")


# ---------------------------------------------------------------- division
def fig_division():
    # review (2026-11-06): one file holds the re-solved fragmented case
    # (placeholder site removed) and its common-basis re-billing
    _df = os.environ.get("V9_DIV")
    if _df:
        D = json.load(open(_df))["cases"]
        A = D["A_fragmented"]
    else:
        D = json.load(open(f"{V9}/campaign_division_v9.json"))["cases"]
        A = json.load(open(f"{V9}/campaign_division_v9_A.json"))["cases"]["A_fragmented"]
    a_cb = (A.get("common_basis") or {}).get("differentiating_cost")
    a_cb = a_cb / 1e3 if a_cb else None
    pr = A["per_route"].values()
    a_inc = A["differentiating_cost"] / 1e3
    a_lb = (A["differentiating_cost"] - sum(r["abs_gap"] for r in pr)) / 1e3
    a_peak = sum(r["peak_depot_kW"] for r in pr if r.get("peak_depot_kW"))
    C = D["C_shared_infra_frozen_z"]
    Dd = D["D_full_coordination"]
    cases = [("Fragmented", a_lb, a_inc, A["n_ffh"], a_peak / 1e3, GRAY),
             ("Shared pool,\nfixed assign.",
              (C["differentiating_cost"] - C["abs_gap"]) / 1e3,
              C["differentiating_cost"] / 1e3, C["n_ffh"],
              C["peak_depot_kW"] / 1e3, BLUE),
             ("Full\ncoordination",
              (Dd["differentiating_cost"] - Dd["abs_gap"]) / 1e3,
              Dd["differentiating_cost"] / 1e3, Dd["n_ffh"],
              Dd["peak_depot_kW"] / 1e3, TEAL)]
    best = min(c[2] for c in cases[1:])
    fig, (a, b, c) = plt.subplots(1, 3, figsize=(COLW, 1.75),
                                  gridspec_kw={"width_ratios": [1.3, 1, 1],
                                               "wspace": 0.7})
    x = np.arange(3)
    for i, cs in enumerate(cases):
        a.vlines(i, cs[1], cs[2], color=cs[5], lw=3.2, alpha=0.45)
        a.scatter([i], [cs[2]], s=18, color=cs[5], zorder=3, marker="o")
        a.scatter([i], [cs[1]], s=18, color=cs[5], zorder=3, marker="_")
    if a_cb:
        a.scatter([0], [a_cb], s=22, facecolors="none", edgecolors=GRAY,
                  zorder=3, marker="s", lw=0.8)
        a.text(0.15, a_cb, "one\nconnection", fontsize=5.4, color=GRAY,
               va="center", ha="left")
        a.set_ylim(top=a_cb + 45)
    a.axhline(a_lb, color=GRAY, lw=0.6, ls=":")
    a.axhline(best, color=BLUE, lw=0.6, ls=":")
    a.annotate("", xy=(0.5, best), xytext=(0.5, a_lb),
               arrowprops=dict(arrowstyle="<->", color=ORANGE, lw=0.8))
    a.text(0.6, (a_lb + best) / 2, f"$\\geq${a_lb - best:.0f}",
           color=ORANGE, fontsize=7, va="center")
    a.set_ylabel("Cost [kCAD/yr]")
    a.set_xticks(x, ["Frag.", "Pool", "Coord."], fontsize=6.2)
    a.set_xlim(-0.5, 2.5)
    a.text(0.0, 1.04, "(a)", transform=a.transAxes, fontweight="bold",
           fontsize=8.5)
    b.bar(x, [cs[3] for cs in cases], 0.72, color=[cs[5] for cs in cases])
    for i, cs in enumerate(cases):
        b.text(i, cs[3] + 2, f"{cs[3]}", ha="center", fontsize=6.8)
    b.set_ylabel("FFH buses")
    b.set_xticks([])
    b.set_ylim(0, max(cs[3] for cs in cases) * 1.18)
    b.text(0.0, 1.04, "(b)", transform=b.transAxes, fontweight="bold",
           fontsize=8.5)
    c.bar(x, [cs[4] for cs in cases], 0.72, color=[cs[5] for cs in cases])
    for i, cs in enumerate(cases):
        c.text(i, cs[4] + 0.08, f"{cs[4]:.1f}", ha="center", fontsize=6.8)
    c.set_ylabel("Depot peak [MW]")
    c.set_xticks([])
    c.set_ylim(0, max(cs[4] for cs in cases) * 1.18)
    c.text(0.0, 1.04, "(c)", transform=c.transAxes, fontweight="bold",
           fontsize=8.5)
    for cs in cases:
        print(f"  {cs[0].replace(chr(10), ' '):28s} LB {cs[1]:7.1f} inc "
              f"{cs[2]:7.1f} ffh {cs[3]} peak {cs[4]:.2f} MW")
    print(f"  certified coordination saving >= {a_lb - best:.1f} kCAD/yr")
    save(fig, "fig_division")


SCEN_DAYS = {b: INP["scenarios"][b]["days"] for b in BANDS}

if __name__ == "__main__":
    fig_weather()
    fig_price()
    fig_robust()
    fig_division()
