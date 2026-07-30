"""
v7 traction interface: route mean x system-wide band factor.

  e_hat[r, w] = ebar_r * f_w,   f_w = ebar_w / ebar_all   (multiplicative)
  e_add[r, w] = ebar_r + (ebar_w - ebar_all)              (additive check)

Route 52's mean uses a TEMPORAL split: estimated on the Jan-Mar 2025 winter,
evaluated on Nov-Dec 2025. Division routes absent from telemetry (or with
n < 30) fall back to the system mean. Writes traction_v7.json with the band
tables and a validation-metric block comparing the regression interface and
the v7 interface on run, route, band, and block-day (bus-day) aggregates.
"""

import json
import os

import numpy as np
import pandas as pd

REPO = "/Users/natomanzolli/Documents/GitHub/heating_system_study"
BANDS = {"mild": (0, 5, 2.5), "cold": (-5, 0, -2.5), "verycold": (-10, -5, -7.5),
         "extreme": (-15, -10, -12.5), "severe": (-99, -15, -17.5),
         "offseason": (5, 99, 17.4)}
# the 14 routes of the division instance (garage_inputs branch prefixes)
DIV_ROUTES = ["52", "35", "36", "84", "96", "99", "108", "120", "165",
              "927", "935", "952", "984", "996"]
MIN_N = 30

df = pd.read_excel(f"{REPO}/data/TTC_Preprocessed_version2_2.xlsx")
d = df[(df["Distance [km]"] > 3) & (df["DT Energy Used [kWh]"] > 0)
       & df["Avg Ambient Temp [degC]"].notna()
       & (df["Vehicle Speed [km/h]"] > 5)].copy()
d["ekm"] = d["DT Energy Used [kWh]"] / d["Distance [km]"]
d = d[(d["ekm"] > 0.3) & (d["ekm"] < 4)]
d["route"] = d["Route  Number"].astype(str).str.strip().str.replace(
    r"\.0$", "", regex=True)
d["Date"] = pd.to_datetime(d["Date"])
T = d["Avg Ambient Temp [degC]"]

def band_of(t):
    for nm, (lo, hi, _) in BANDS.items():
        if lo <= t < hi:
            return nm
    return "offseason"
d["band"] = T.map(band_of)

ebar_all = d["ekm"].mean()
f = {nm: d.loc[d["band"] == nm, "ekm"].mean() / ebar_all for nm in BANDS}
band_n = {nm: int((d["band"] == nm).sum()) for nm in BANDS}

# route means; Route 52 from the first winter only (temporal split)
r52 = d[d["route"] == "52"]
w1 = r52[r52["Date"] < "2025-07-01"]          # Jan-Mar 2025 winter
w2 = r52[r52["Date"] >= "2025-07-01"]         # Nov-Dec 2025 winter
route_means, route_n = {}, {}
for r in DIV_ROUTES:
    s = d[d["route"] == r]
    if r == "52":
        route_means[r], route_n[r] = float(w1["ekm"].mean()), int(len(w1))
    elif len(s) >= MIN_N:
        route_means[r], route_n[r] = float(s["ekm"].mean()), int(len(s))
    else:
        route_means[r], route_n[r] = float(ebar_all), int(len(s))

# ---------------- validation metrics: regression (LOO) vs v7 ----------------
loo = d[d["route"] != "52"]
X = np.column_stack([np.ones(len(loo)),
                     np.maximum(0, 5 - loo["Avg Ambient Temp [degC]"]),
                     loo["Vehicle Speed [km/h]"]])
c, *_ = np.linalg.lstsq(X, loo["ekm"], rcond=None)
d["reg"] = c[0] + c[1] * np.maximum(0, 5 - T) + c[2] * d["Vehicle Speed [km/h]"]
# v7 prediction per run: route mean (temporal for 52, in-sample elsewhere,
# system mean for thin routes) x band factor
rm_all = {r: (float(w1["ekm"].mean()) if r == "52" else
              float(d.loc[d["route"] == r, "ekm"].mean()))
          for r in d["route"].unique()
          if r == "52" or (d["route"] == r).sum() >= MIN_N}
d["v7"] = d.apply(lambda x: rm_all.get(x["route"], ebar_all) * f[x["band"]],
                  axis=1)

def spearman(a, b):
    ra, rb = pd.Series(a).rank(), pd.Series(b).rank()
    return float(np.corrcoef(ra, rb)[0, 1])

M = {}
for nm, col in (("regression", "reg"), ("v7", "v7")):
    m = {}
    m["run_MAE_kWh_km"] = float((d[col] - d["ekm"]).abs().mean())
    g = d[d["route"].map(lambda r: (d["route"] == r).sum() >= MIN_N)]
    rr = g.groupby("route").agg(obs=("ekm", "mean"), prd=(col, "mean"))
    m["route_mean_MAPE_pct"] = float(
        ((rr["prd"] - rr["obs"]).abs() / rr["obs"]).mean() * 100)
    bb = d.groupby("band").agg(obs=("ekm", "mean"), prd=(col, "mean"))
    m["band_mean_MAPE_pct"] = float(
        ((bb["prd"] - bb["obs"]).abs() / bb["obs"]).mean() * 100)
    bd = d.assign(E=d["ekm"] * d["Distance [km]"],
                  Ep=d[col] * d["Distance [km]"]).groupby(
        ["Bus  Number", d["Date"].dt.date]).agg(E=("E", "sum"), Ep=("Ep", "sum"))
    m["blockday_MAPE_pct"] = float(((bd["Ep"] - bd["E"]).abs() / bd["E"]).mean() * 100)
    m["route_rank_spearman"] = spearman(rr["obs"], rr["prd"])
    M[nm] = {k: round(v, 3) for k, v in m.items()}

# Route 52 out-of-time check: winter-1 mean applied to winter-2 runs
w2b = w2.copy(); w2b["band"] = w2["Avg Ambient Temp [degC]"].map(band_of)
pred2 = w2b["band"].map(lambda b: route_means["52"] * f[b])
M["r52_temporal"] = {
    "w1_n": int(len(w1)), "w2_n": int(len(w2)),
    "w2_energy_ratio_pred_over_obs": round(float(
        (pred2 * w2b["Distance [km]"]).sum()
        / (w2b["ekm"] * w2b["Distance [km]"]).sum()), 4)}

out = {"ebar_all": round(float(ebar_all), 4),
       "band_factors": {k: round(float(v), 4) for k, v in f.items()},
       "band_n": band_n, "route_means": {k: round(v, 4) for k, v in route_means.items()},
       "route_n": route_n, "min_n_fallback": MIN_N,
       "r52_winter1_mean": round(float(w1["ekm"].mean()), 4),
       "metrics": M,
       "e_hat": {r: {nm: round(route_means[r] * f[nm], 4) for nm in BANDS}
                 for r in DIV_ROUTES},
       "e_hat_additive": {r: {nm: round(route_means[r] + (f[nm]-1)*ebar_all, 4)
                              for nm in BANDS} for r in DIV_ROUTES}}
json.dump(out, open("traction_v7.json", "w"), indent=1)

# ---- supplementary table: band factors + accuracy metrics ------------------
# The paper acknowledges only the adopted route-band interface, so the table
# reports its accuracy without reference to any other model form. The full
# metric block (including comparisons) stays archived in traction_v7.json.
Mv7 = M["v7"]
frows = "\n".join(
    f"{nm.capitalize().replace('Verycold','Very cold').replace('Offseason','Off-season')} & "
    f"{band_n[nm]:,} & {f[nm]:.3f} \\\\" for nm in BANDS)
vrows = "\n".join(
    f"{lbl} & {Mv7[k]:{fmt}} \\\\" for lbl, k, fmt in (
        ("Run-level MAE (kWh/km)", "run_MAE_kWh_km", ".3f"),
        ("Route-level mean MAPE (\\%)", "route_mean_MAPE_pct", ".1f"),
        ("Band-level mean MAPE (\\%)", "band_mean_MAPE_pct", ".1f"),
        ("Block-day energy MAPE (\\%)", "blockday_MAPE_pct", ".1f"),
        ("Route-ranking Spearman", "route_rank_spearman", ".2f")))
oot = 100*(M["r52_temporal"]["w2_energy_ratio_pred_over_obs"]-1)
body = ("\\begin{table}[!ht]\n"
 "\\caption{Band factors $f_\\omega$ with run counts (left) and accuracy\n"
 "of the route--band traction interface (right).}\n"
 "\\label{tab:tractionv7}\n\\centering\n\\footnotesize\n"
 "\\begin{minipage}[t]{0.38\\textwidth}\n"
 "\\begin{tabular}[t]{@{}lrr@{}}\n\\toprule\n"
 "\\textbf{Band} & \\textbf{$n$} & \\textbf{$f_\\omega$} \\\\\n\\midrule\n"
 f"{frows}\n"
 "\\bottomrule\n\\end{tabular}\n\\end{minipage}\\hfill\n"
 "\\begin{minipage}[t]{0.58\\textwidth}\n"
 "\\begin{tabular}[t]{@{}lr@{}}\n\\toprule\n"
 "\\textbf{Metric} & \\textbf{Route--band} \\\\\n\\midrule\n"
 f"{vrows}\n"
 "\\bottomrule\n\\end{tabular}\n\\end{minipage}\n\\end{table}\n")
stamp = ("% GENERATED by make_traction_v7.py from the telemetry pipeline.\n"
         "% Do not edit by hand - regenerate instead.\n")
for dst in ("supp_tables", "../Overleaf/short/supp_tables"):
    if os.path.isdir(dst):
        open(os.path.join(dst, "tab_tractionv7.tex"), "w").write(stamp + body)
print("wrote tab_tractionv7.tex")
print("ebar_all", out["ebar_all"], "| factors", out["band_factors"])
print("R52: w1 mean", out["r52_winter1_mean"], "| oot energy ratio",
      M["r52_temporal"]["w2_energy_ratio_pred_over_obs"])
print(json.dumps(M, indent=1))
