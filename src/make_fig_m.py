"""
Main-paper analytical figures (advisor visual-redesign package):

  fig3_ops.pdf       weather-adaptive operation of the economic baseline
                     (a) delivered cabin heat by source per winter band
                     (b) diesel use and minimum arrival margin per band
  fig4_frontier.pdf  integrated cost-emissions frontier: incremental cost
                     vs. onboard emissions, four representative designs,
                     three transition regimes, selected carbon-price points

Everything is read from the campaign archive; nothing is typed in.
  FIG_RES  results file (default campaign_v5_results.json)

Outputs land in ieee_figs/ and are copied into both manuscript trees.
"""

import json
import os
import shutil

import matplotlib.pyplot as plt

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

OUT = "ieee_figs"
os.makedirs(OUT, exist_ok=True)
# submission master (../Overleaf); superseded long draft is archived
FIGDIRS = [d for d in ("../overleaf-git/figures",)
           if os.path.isdir(d)]

RES = os.environ.get("FIG_RES", "campaign_v5_results.json")
DIVF = os.environ.get("FIG_DIV", "campaign_division_v5.json")
DETB = os.environ.get("FIG_DETBAND", "detband_v5.json")
RELB = os.environ.get("FIG_REL_BASE", "reliability_reserve10.json")
RELZ = os.environ.get("FIG_REL_ZERO", "reliability_zeroemission.json")
D = json.load(open(RES))
RUNS = {r["label"]: r for r in D["runs"]
        if "error" not in r and not r.get("infeasible")}
OPS = D.get("ops_metrics_econ") or D.get("ops_metrics_policy", {})

BANDS = ["mild", "cold", "verycold", "extreme", "severe"]
BAND_LBL = {"mild": "Mild", "cold": "Cold", "verycold": "Very cold",
            "extreme": "Extreme", "severe": "Severe"}


def save(fig, name):
    for ext in ("pdf", "png"):
        fig.savefig(f"{OUT}/{name}.{ext}", dpi=600 if ext == "png" else None,
                    bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
    for d in FIGDIRS:
        shutil.copy(f"{OUT}/{name}.pdf", os.path.join(d, f"{name}.pdf"))
    print("wrote", name, "->", ", ".join([OUT] + FIGDIRS))


def panel_label(ax, s):
    ax.text(0.0, 1.04, s, transform=ax.transAxes, fontsize=9,
            fontweight="bold", va="bottom", ha="left")


# ------------------------------------------------------- Fig. 3 (operations)
def fig_ops(name="fig3_ops"):
    e = RUNS["econ_lam0"]
    so = e["scen_ops"]
    x = range(len(BANDS))
    pre = [so[w]["precond_kWh"] for w in BANDS]
    qel = [so[w]["q_el_kWh"] for w in BANDS]
    qff = [so[w]["q_ffh_kWh"] for w in BANDS]
    dsl = [so[w]["diesel_L"] for w in BANDS]
    xt = [f"{BAND_LBL[w]}\n{so[w]['T']:+.1f}°C" for w in BANDS]

    fig, (a, b) = plt.subplots(2, 1, figsize=(3.5, 2.5), sharex=True)

    a.bar(x, pre, color=TEAL, label="Preconditioning", width=0.6)
    a.bar(x, qel, bottom=pre, color=BLUE, label="Electric heating",
          width=0.6)
    a.bar(x, qff, bottom=[p + q for p, q in zip(pre, qel)], color=ORANGE,
          label="Fuel-fired heating", width=0.6)
    a.set_ylabel("Cabin heat\n(kWh/day)")
    a.legend(loc="lower left", bbox_to_anchor=(0.0, 1.0), ncol=3,
             handlelength=1.0, columnspacing=0.9, fontsize=6.4)
    a.text(-0.02, 1.0, "(a)", transform=a.transAxes, fontsize=9,
           fontweight="bold", ha="right", va="bottom")
    tots = [p + q + f for p, q, f in zip(pre, qel, qff)]
    a.set_ylim(0, max(tots) * 1.14)
    # FFH share printed where the burner contributes materially
    for i, w in enumerate(BANDS):
        if tots[i] > 0 and qff[i] / tots[i] > 0.05:
            a.text(i, tots[i] + max(tots) * 0.015,
                   f"{100*qff[i]/tots[i]:.0f}%", ha="center", va="bottom",
                   fontsize=6.3, color=ORANGE)

    b.bar(x, dsl, color=ORANGE, width=0.6, label="Diesel")
    b.set_ylabel("Diesel\n(L/day)", color=ORANGE)
    b.tick_params(axis="y", colors=ORANGE)
    b.set_xticks(list(x))
    b.set_xticklabels(xt, fontsize=6.4)
    if OPS:
        b2 = b.twinx()
        b2.plot(list(x), [OPS[w]["min_reserve_kWh"] for w in BANDS],
                color=BLUE, marker="o", ms=3.5, lw=1.0,
                label="Min. arrival margin")
        b2.set_ylabel("Min. margin\n(kWh)",
                      color=BLUE)
        b2.tick_params(axis="y", colors=BLUE)
        b2.spines["right"].set_visible(True)
        b2.spines["right"].set_linewidth(0.6)
        b2.grid(False)
        b2.set_ylim(bottom=0)
    b.text(-0.02, 1.0, "(b)", transform=b.transAxes, fontsize=9,
           fontweight="bold", ha="right", va="bottom")

    fig.tight_layout(h_pad=0.6)
    save(fig, name)


# ------------------------------------------------- Fig. 4 (frontier, merged)
def _design_note(r):
    fl = r["fleet"]
    parts = []
    std_f = fl.get("NF-std-FFH", 0)
    std_e = fl.get("NF-std-eOnly", 0)
    ext_f = fl.get("NF-ext-FFH", 0)
    ext_e = fl.get("NF-ext-eOnly", 0)
    if std_f or ext_f:
        parts.append(f"{std_f + ext_f} FFH")
    if std_e or ext_e:
        parts.append(f"{std_e + ext_e} el.-only"
                     + (f" ({ext_e} ext.)" if ext_e else ""))
    ch = {}
    for key, v in r["chargers"].items():
        n, p = key.split(":")
        tag = f"{v}$\\times${p}" + ("T" if n != "depot" else "")
        ch[tag] = None
    return ", ".join(parts) + "\n" + ", ".join(ch)


def fig_frontier(name="fig4_frontier"):
    base = RUNS["econ_lam0"]
    f0 = base["F1"]

    eps = sorted((r for l, r in RUNS.items() if l.startswith("eps_")),
                 key=lambda r: -r["co2_t"])
    pts = [base] + eps
    xs = [r["co2_t"] for r in pts]
    ys = [(r["F1"] - f0) / 1e3 for r in pts]

    # text-box anchor points in DATA coordinates, chosen to sit in empty
    # regions of the plane so no box crosses the frontier curve
    # v9 representatives (Table IV columns D1-D4)
    DEP = os.environ.get("FIG_DEP", "eps_0.70")
    MIX = os.environ.get("FIG_MIX", "eps_0.35")
    TER = os.environ.get("FIG_TER", "eps_0.10")
    named = {"econ_lam0": ("(D0) Economic\nbaseline", (18.6, 9.0), "right"),
             DEP: ("(D1) Depot charger\nreconfiguration", (10.2, 20.0), "left"),
             MIX: ("(D2) Mixed\nfleet", (6.2, 33.0), "left"),
             TER: ("(D3) Terminal\ncharger upgrade", (4.2, 45.0), "left"),
             "eps_0.00": ("(D4) Full heating\nelectrification", (2.2, 58.0),
                          "left")}

    fig, ax = plt.subplots(figsize=(3.5, 2.35))

    co2_dep = RUNS[DEP]["co2_t"]
    co2_mix = RUNS[MIX]["co2_t"]
    co2_max = base["co2_t"]
    ax.axvspan(co2_dep, co2_max * 1.04, color="0.94", zorder=0)
    ax.axvspan(co2_mix, co2_dep, color="0.88", zorder=0)
    ax.axvspan(-co2_max * 0.02, co2_mix, color="0.82", zorder=0)
    ytop = max(ys) * 1.32
    for xc, lbl, yf in (
            (0.5 * (co2_dep + co2_max), "Depot charging", 1.00),
            (0.5 * (co2_mix + co2_dep), "Mixed fleet", 1.00),
            (0.5 * co2_mix, "Terminal\ncharging", 1.00)):
        ax.text(xc, ytop * yf, lbl, ha="center", va="top", fontsize=6.0,
                color="0.25")

    ax.plot(xs, ys, color=GRAY, lw=0.8, zorder=2)
    ax.plot(xs, ys, "o", color=GRAY, ms=2.6, zorder=3)

    for lb, (txt, pos, ha) in named.items():
        r = RUNS[lb]
        xr, yr = r["co2_t"], (r["F1"] - f0) / 1e3
        ax.plot(xr, yr, "o", color=BLUE, ms=5.5, zorder=4)
        ax.annotate(txt, (xr, yr),
                    textcoords="data", xytext=pos, fontsize=6.0,
                    ha=ha, va="bottom", zorder=6,
                    arrowprops=dict(arrowstyle="-", lw=0.5, color="0.4",
                                    shrinkB=3),
                    bbox=dict(boxstyle="round,pad=0.22", fc="white",
                              ec="0.6", lw=0.4, alpha=1.0))

    for lb, lam in (("lam_3500", 3500),):
        if lb in RUNS:
            r = RUNS[lb]
            ax.plot(r["co2_t"], (r["F1"] - f0) / 1e3, "D", mfc="white",
                    mec=ORANGE, ms=4.5, mew=1.0, zorder=4)
            ax.annotate(f"$\\lambda$={lam}", (r["co2_t"],
                                              (r["F1"] - f0) / 1e3),
                        textcoords="offset points", xytext=(-30, -9),
                        fontsize=6.0, color=ORANGE)

    ax.set_xlabel("Onboard emissions (t$\\mathrm{CO_2}$/yr)")
    ax.set_ylabel("Incremental cost (kCAD/yr)")
    ax.set_xlim(-co2_max * 0.02, co2_max * 1.04)
    ax.set_ylim(min(ys) - 1.5, ytop * 1.02)
    fig.tight_layout()
    save(fig, name)


# ---------------------------------------- Fig. S (division heterogeneity)
def fig_routes(name="figS_routes"):
    """Per-route FFH share of the fragmented case vs. the coordinated
    fleet-wide share: the route heterogeneity that coordination exploits."""
    if not os.path.exists(DIVF):
        print("skip fig_routes: no division file")
        return
    dv = json.load(open(DIVF))["cases"]
    A = dv.get("A_fragmented", {})
    # the coordinated reference is the best coordinated solution found, which
    # need not be case D: constrained variants are feasible for it and can
    # finish lower at this instance size
    _coord = [c for k, c in dv.items()
              if k != "A_fragmented" and c.get("differentiating_cost")]
    Dc = min(_coord, key=lambda c: c["differentiating_cost"]) if _coord else {}
    per = A.get("per_route")
    if not per or not Dc:
        print("skip fig_routes: incomplete cases")
        return
    routes = sorted(per, key=lambda r: 100 * per[r]["n_ffh"]
                    / max(1, per[r]["n_buses"]))
    share = [100 * per[r]["n_ffh"] / max(1, per[r]["n_buses"])
             for r in routes]
    nb = [per[r]["n_buses"] for r in routes]
    coord = 100 * Dc["n_ffh"] / max(1, Dc["n_buses"])

    fig, ax = plt.subplots(figsize=(4.6, 2.6))
    y = range(len(routes))
    ax.barh(list(y), share, color=ORANGE, height=0.62)
    ax.set_yticks(list(y))
    ax.set_yticklabels([f"{r}  ({n} buses)" for r, n in zip(routes, nb)],
                       fontsize=6.6)
    ax.axvline(coord, color=BLUE, lw=1.2, ls="--")
    # anchor the label in the empty band at the bottom, where the zero-share
    # routes leave clear space; at the top it sat on the longest bar
    ax.text(coord + 2, 0.15, f"coordinated fleet: {coord:.0f}%",
            color=BLUE, fontsize=6.6, va="center", ha="left")
    ax.set_xlabel("FFH-equipped share of the route's fleet (%)")
    ax.set_xlim(0, 105)
    ax.grid(axis="x", color="#DDDDDD", lw=0.4)
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    save(fig, name)


# --------------------------------- Fig. (weather-uncertainty value, IV-B)
def fig_uncertainty(name="fig5_uncertainty"):
    """Out-of-sample compliance by band: economic baseline vs. the
    full-electrification design, floor and reserve criteria."""
    ra = json.load(open(RELB))["levels"]["heat_cv_0.00"]
    rz = json.load(open(RELZ))["levels"]["heat_cv_0.00"]

    fig, b = plt.subplots(figsize=(3.5, 1.85))
    x = range(len(BANDS))
    RED = "#8C2D2D"
    series = [("Baseline, SoC floor",
               [100 * ra[w]["p_soc_floor_ok"] for w in BANDS], BLUE, "o"),
              ("Baseline, incl. reserve",
               [100 * ra[w]["p_all_trips_served"] for w in BANDS], TEAL, "s"),
              ("Full elec., SoC floor",
               [100 * rz[w]["p_soc_floor_ok"] for w in BANDS], ORANGE, "^"),
              ("Full elec., incl. reserve",
               [100 * rz[w]["p_all_trips_served"] for w in BANDS], RED, "D")]
    for lb, ys, c, mk in series:
        b.plot(list(x), ys, "-", color=c, marker=mk, ms=3.4, lw=1.1,
               label=lb)
    b.set_xticks(list(x))
    b.set_xticklabels([BAND_LBL[w] for w in BANDS], fontsize=7)
    b.set_ylabel("Compliant days (%)")
    b.set_ylim(25, 103)
    b.legend(fontsize=5.8, loc="lower left", ncol=1, handlelength=1.6)
    fig.tight_layout()
    save(fig, name)


if __name__ == "__main__":
    fig_ops()
    fig_frontier()
    fig_routes()
    fig_uncertainty()
