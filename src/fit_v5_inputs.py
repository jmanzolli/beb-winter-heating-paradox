"""
v5 input regeneration (revision protocol items 3.9 and 4.1).

1. Traction interface refit LEAVING ROUTE 52 OUT (route column observed in
   telemetry) — used for the Route 52 planning instance so the diesel
   comparison is not trained on the evaluated route. Division instance keeps
   the full-sample fit (no single held-out route exists for a 14-route
   system); both fits are reported.
2. Off-season scenario: Apr 1 - Oct 31 (214 days), representative temperature
   from ECCC climate-daily (Toronto City 6158355), Apr-Oct 2024 & 2025 daily
   means (eccc_offseason_{2024,2025}.json). Cabin heating set to zero
   (documented assumption; air conditioning not modeled). Scenario weights
   then sum to 365 days.

Writes route52_inputs_v5.json and garage_inputs_v5.json.
"""

import json

import numpy as np
import pandas as pd

REPO = "/Users/natomanzolli/Documents/GitHub/heating_system_study"


def load_runs():
    df = pd.read_excel(f"{REPO}/data/TTC_Preprocessed_version2_2.xlsx")
    d = df[(df["Distance [km]"] > 3) & (df["DT Energy Used [kWh]"] > 0)
           & df["Avg Ambient Temp [degC]"].notna()
           & (df["Vehicle Speed [km/h]"] > 5)].copy()
    d["ekm"] = d["DT Energy Used [kWh]"] / d["Distance [km]"]
    d = d[(d["ekm"] > 0.3) & (d["ekm"] < 4)]
    d["route"] = d["Route  Number"].astype(str).str.strip().str.replace(
        r"\.0$", "", regex=True)
    return d


def fit(d, label):
    T = d["Avg Ambient Temp [degC]"].values
    v = d["Vehicle Speed [km/h]"].values
    y = d["ekm"].values
    X = np.column_stack([np.ones(len(d)), np.maximum(0, 5 - T), v])
    c, *_ = np.linalg.lstsq(X, y, rcond=None)
    pred = X @ c
    r2 = 1 - ((y - pred) ** 2).sum() / ((y - y.mean()) ** 2).sum()
    return {"a0": round(float(c[0]), 5), "a1_cold": round(float(c[1]), 5),
            "a2_speed": round(float(c[2]), 5), "T_ref": 5.0,
            "fit_runs": int(len(d)), "fit_R2": round(float(r2), 3),
            "fit_note": label}


def offseason_T():
    vals = []
    for y in (2024, 2025):
        d = json.load(open(f"eccc_offseason_{y}.json"))
        vals += [f["properties"]["MEAN_TEMPERATURE"] for f in d["features"]
                 if f["properties"]["MEAN_TEMPERATURE"] is not None]
    return round(sum(vals) / len(vals), 1), len(vals)


d = load_runs()
tr_full = fit(d, "full sample (all routes)")
tr_loo = fit(d[d["route"] != "52"], "leave-Route-52-out")
n52 = int((d["route"] == "52").sum())
T_off, n_off = offseason_T()
OFF = {"T": T_off, "days": 214, "heat": False,
       "note": f"Apr-Oct 2024+2025 ECCC daily means, n={n_off}; cabin "
               "heating zero (assumption); AC not modeled"}

print("full fit:", tr_full)
print("LOO-52 fit:", tr_loo, f"(excluded {n52} Route 52 runs)")
print("offseason:", OFF)

for src, dst, tr in [("route52_inputs.json", "route52_inputs_v5.json", tr_loo),
                     ("garage_inputs.json", "garage_inputs_v5.json", tr_full)]:
    inp = json.load(open(src))
    inp["traction"] = tr
    inp["traction_full_sample"] = tr_full
    inp["traction_loo52"] = tr_loo
    inp["scenarios"]["offseason"] = OFF
    inp["ffh_rated_kw"] = 12.0
    inp["ffh_rated_note"] = ("winter-conditions FFH useful output, Liu et "
                             "al. (Paper 1)")
    inp["el_heater_rated_kw"] = 23.0
    inp["el_heater_note"] = ("p99 of eHeat energy / electric-heating time "
                             "over 9,001 telemetry runs")
    json.dump(inp, open(dst, "w"), indent=2)
    print("wrote", dst)
