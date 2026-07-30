"""
Out-of-sample reliability of a selected design under residual energy-demand
uncertainty (revision protocol Section 4.2).

Weather scenarios represent temperature, not the trip-to-trip dispersion that
remains after conditioning on temperature and speed. This harness evaluates a
FIXED first-stage design against resampled residual demand.

Traction uncertainty is EMPIRICAL and genuinely out of sample. Each telemetry
row is one bus-day (median 13 h, 184 km; one row per date and vehicle), so
the ratio of observed to predicted energy intensity is a block-day-level
residual of the leave-Route-52-out fit that built the planning instance.
Applying one drawn residual to every trip of a block therefore reproduces the
correct, fully correlated within-block structure rather than assuming
independent trip errors.

Heating uncertainty is PARAMETRIC and labelled as a stress test, not as an
empirical quantification. It cannot be estimated from the available data:
fuel-fired heater output is not metered, and on Route 52 the electric heater
runs a median of 0.11 h/day (median 2.5 kWh), so no delivered-heat residual
can be formed for the FFH-served operation that dominates this route. An
earlier attempt to use electric-heat energy as a proxy produced a mean ratio
of 0.59, which measures heater duty cycle rather than demand-model error and
would bias reliability optimistically; it is not used. Instead the cabin-heat
demand is perturbed by a multiplicative lognormal factor at declared
coefficients of variation, reported as a sensitivity across levels.

MISSING DATA (protocol Section 1): a defensible empirical heat-demand
uncertainty needs either the posterior predictive draws of the Bayesian
thermal model or metered FFH fuel per trip. Neither is archived in the study
repository.

Decision timing: the design and the day-ahead block-class assignment are held
fixed at the planning solution; charging, preconditioning, and heat dispatch
re-optimize against the realized loads. Energy shortfall is measured with
penalized slack on the arrival reserve, the SoC floor, and overnight closure,
so an unserviceable realization is quantified rather than rejected.

Usage:
  ROUTE_INPUTS=route52_inputs_v5.json python3 reliability_v5.py [N_per_band]
"""

import json
import os
import sys
import time

os.environ.setdefault("ROUTE_INPUTS", "route52_inputs_v5.json")

import numpy as np
import pandas as pd

import route52_prototype as R

if os.environ.get("REL_RESERVE"):
    R.RESERVE_RETURN = float(os.environ["REL_RESERVE"])

REPO = "/Users/natomanzolli/Documents/GitHub/heating_system_study"
# Overridable so an alternative design (e.g. the larger-reserve one) can be
# evaluated against the SAME service criterion. Note the harness deliberately
# keeps R.RESERVE_RETURN at its default: the planning reserve a design was
# built with is a margin, not a service requirement, so every design is
# judged on whether it completes the day above the common floor. Judging the
# reserve-50 design against a 50 kWh end-of-day requirement would measure a
# stricter criterion, not better service.
RESULTS = os.environ.get("REL_RESULTS", "campaign_v5_results.json")
OUT_FILE = os.environ.get("REL_OUT", "reliability_v5.json")
DESIGN_LABEL = os.environ.get("REL_DESIGN", "policy_lam100")
# carbon price used inside the planning-assignment and dispatch re-solves;
# set REL_LAM=0 when evaluating the economic baseline so day-ahead
# assignment and recourse use the same objective the design was built with
REL_LAM = float(os.environ.get("REL_LAM", 100.0))
N_DEFAULT = 200
SEED = int(os.environ.get("REL_SEED", 20260725))
# declared cabin-heat stress levels (coefficient of variation); 0 = empirical
# traction uncertainty only. Design COMPARISONS should use 0 alone: the other
# levels are declared assumptions, not measurements.
HEAT_CVS = [float(x) for x in
            os.environ.get("REL_HEAT_CVS", "0.0,0.20,0.40").split(",")]
# Planning/dispatch reserve used inside the simulation. Raising it makes the
# day-ahead plan and the recourse hold back more energy; it does NOT change
# how a day is judged. Service is judged by the SoC floor alone
# (p_soc_floor_ok below), which is common to every setting, so a conservative
# operating policy is not penalised for meeting a stricter internal target.
REL_RESERVE = os.environ.get("REL_RESERVE")
BANDS = [w for w in R.SCEN if w not in R.HEATLESS]


# ---------------------------------------------------------------- residuals
def traction_pool():
    """Block-day multiplicative residuals of the planning interface,
    evaluated on Route 52.

    Under the v5 regression instance the prediction is the leave-Route-52-out
    fit (out of sample by construction). Under a v7 instance the prediction is
    the route--band interface (route mean x band factor), so the pool measures
    the run-level dispersion the band means deliberately exclude.

    REL_POOL=<file>: if the file exists, load the pool from it instead of the
    telemetry workbook (the workbook lives on the analysis machine, not the
    solve host); if it does not exist, compute the pool and write it there.
    """
    pf = os.environ.get("REL_POOL")
    if pf and os.path.exists(pf):
        pj = json.load(open(pf))
        return np.asarray(pj["ratios"]), pj["stats"]
    df = pd.read_excel(f"{REPO}/data/TTC_Preprocessed_version2_2.xlsx")
    df["route"] = (df["Route  Number"].astype(str).str.strip()
                   .str.replace(r"\.0$", "", regex=True))
    t = df[(df["route"] == "52") & (df["Distance [km]"] > 3)
           & (df["DT Energy Used [kWh]"] > 0)
           & df["Avg Ambient Temp [degC]"].notna()
           & (df["Vehicle Speed [km/h]"] > 5)].copy()
    t["ekm"] = t["DT Energy Used [kWh]"] / t["Distance [km]"]
    t = t[(t["ekm"] > 0.3) & (t["ekm"] < 4)]
    t["pred"] = [R.e_traction_per_km(T, v) for T, v in
                 zip(t["Avg Ambient Temp [degC]"], t["Vehicle Speed [km/h]"])]
    t["ratio"] = t["ekm"] / t["pred"]
    t = t[(t["ratio"] > 0.3) & (t["ratio"] < 3.0)]
    # cold-band subset: residuals may widen at low temperature
    cold = t[t["Avg Ambient Temp [degC]"] < -5]["ratio"]
    stats = {"n_bus_days": int(len(t)),
             "unit": "one telemetry row = one bus-day (median 13 h, 184 km)",
             "mean_ratio": round(float(t["ratio"].mean()), 4),
             "sd_ratio": round(float(t["ratio"].std()), 4),
             "p05": round(float(t["ratio"].quantile(.05)), 3),
             "p95": round(float(t["ratio"].quantile(.95)), 3),
             "cold_subset_n": int(len(cold)),
             "cold_mean_ratio": round(float(cold.mean()), 4) if len(cold) else None,
             "cold_sd_ratio": round(float(cold.std()), 4) if len(cold) else None,
             "source": ("route-band interface (v7) evaluated on Route 52 runs"
                        if (R.INP.get("traction_bands")
                            or R.INP.get("traction_bands_by_route"))
                        else "leave-Route-52-out fit evaluated on Route 52 runs")}
    if pf:
        json.dump({"ratios": [round(float(x), 5) for x in t["ratio"].values],
                   "stats": stats}, open(pf, "w"), indent=1)
    return t["ratio"].values, stats


def draw(rng, pool_t, w, heat_cv):
    """One realization. Traction: one empirical block-day residual per block,
    applied to all its trips (correct correlation unit). Heat: multiplicative
    lognormal factor per block at the declared coefficient of variation
    (parametric stress level; heat_cv = 0 disables heat perturbation)."""
    lm = {}
    sig = np.sqrt(np.log(1.0 + heat_cv ** 2)) if heat_cv > 0 else 0.0
    for b in range(R.N_BLOCKS):
        tm = float(pool_t[rng.integers(len(pool_t))])
        hm = float(np.exp(rng.normal(-0.5 * sig ** 2, sig))) if sig > 0 else 1.0
        for i in range(len(R.BLOCKS[b].trips)):
            lm[(w, b, i)] = (tm, hm)
    return lm


# ------------------------------------------------------------------ harness
def planning_solution(design):
    """Re-solve with the design fixed to recover the day-ahead assignment."""
    m = R.build_model(carbon_price_t=REL_LAM)
    h = m._handles
    for k in range(len(R.BUS_CLASSES)):
        m.addConstr(h["x"][k] == design["x"][k])
    for n in R.SITES:
        for p in R.CH_CLASSES:
            m.addConstr(h["wch"][n, p] == design["wch"][(n, p)])
            m.addConstr(h["ysite"][n, p] == design["ysite"][(n, p)])
        for j in range(len(R.GRID_TIERS)):
            m.addConstr(h["ygrid"][n, j] == design["ygrid"][(n, j)])
    m.Params.OutputFlag = 0
    m.Params.MIPGapAbs = 500
    m.Params.TimeLimit = 1200
    m.Params.Threads = 2
    m.optimize()
    assert m.SolCount > 0, "could not recover planning assignment"
    zmap = {}
    for w in R.SCEN:
        z = m._scen[w]["z"]
        zmap[w] = {b: max(range(len(R.BUS_CLASSES)),
                          key=lambda k: z[b, k].X) for b in range(R.N_BLOCKS)}
    return zmap


def simulate(w, lm, zfix, design):
    m = R.build_model(carbon_price_t=REL_LAM, load_mult=lm, elastic=True,
                      only_scen=w)
    h = m._handles
    for k in range(len(R.BUS_CLASSES)):
        m.addConstr(h["x"][k] == design["x"][k])
    for n in R.SITES:
        for p in R.CH_CLASSES:
            m.addConstr(h["wch"][n, p] == design["wch"][(n, p)])
            m.addConstr(h["ysite"][n, p] == design["ysite"][(n, p)])
        for j in range(len(R.GRID_TIERS)):
            m.addConstr(h["ygrid"][n, j] == design["ygrid"][(n, j)])
    z = m._scen[w]["z"]
    for b, k in zfix[w].items():
        m.addConstr(z[b, k] == 1)
    m.Params.OutputFlag = 0
    m.Params.MIPGap = 0.002
    m.Params.TimeLimit = 300
    m.Params.Threads = 2
    m.optimize()
    if m.SolCount == 0:
        # A realization with no solution is NOT a missing observation: the
        # elastic slack absorbs energy shortfall, so failing to solve means
        # the realized loads violate a constraint slack cannot relax (for
        # example heater rated output against the drawn cabin-heat demand).
        # Dropping these would silently bias reliability upward, so they are
        # recorded as unserved with their solver status.
        return {"solved": False, "feasible": False, "status": int(m.Status),
                "min_reserve_kWh": None, "blocks_infeasible": None,
                "shortfall_kWh": None}
    s = m._scen[w]
    short = m._shortfall.getValue() if hasattr(m._shortfall, "getValue") else 0.0
    K = range(len(R.BUS_CLASSES))
    margins, nfail = [], 0
    for b in range(R.N_BLOCKS):
        cap = R.DERATE[w][0] * sum(R.BUS_CLASSES[k].batt_nom * s["z"][b, k].X
                                   for k in K)
        nt = len(R.BLOCKS[b].trips)
        mn = min(s["Earr"][b, i].X - R.S_LO * cap for i in range(nt))
        margins.append(mn)
        if mn < -1e-3:
            nfail += 1
    return {"solved": True, "shortfall_kWh": round(float(short), 3),
            "feasible": bool(short < 0.1),
            "min_reserve_kWh": round(float(min(margins)), 2),
            "blocks_infeasible": nfail,
            "diesel_L": round(float(s["D"].X), 2)}


if __name__ == "__main__":
    N = int(sys.argv[1]) if len(sys.argv) > 1 else N_DEFAULT
    t0 = time.time()
    rng = np.random.default_rng(SEED)

    rec = {r["label"]: r for r in json.load(open(RESULTS))["runs"]}[DESIGN_LABEL]
    from campaign_v5 import design_from_record
    design = design_from_record(rec)
    print("evaluating design:", rec["fleet"], rec["chargers"], flush=True)

    pool_t, stats = traction_pool()
    print("traction residuals:", json.dumps(stats, indent=1), flush=True)

    zfix = planning_solution(design)
    print("recovered day-ahead assignment", flush=True)

    out = {"design_label": DESIGN_LABEL, "design": rec["fleet"],
           "chargers": rec["chargers"], "n_per_band": N, "seed": SEED,
           "traction_residuals": stats, "levels": {},
           "method": ("empirical block-day traction residuals (out of sample) "
                      "plus parametric lognormal cabin-heat stress levels; "
                      "design and day-ahead assignment fixed; dispatch "
                      "re-optimized; penalized slack measures shortfall"),
           "heat_uncertainty_note": (
               "cabin-heat dispersion is a declared stress level, not an "
               "empirical estimate: FFH output is unmetered and Route 52 "
               "electric-heating runtime is a median 0.11 h/day, so no "
               "delivered-heat residual can be formed")}
    for heat_cv in HEAT_CVS:
        key = f"heat_cv_{heat_cv:.2f}"
        out["levels"][key] = {}
        for w in BANDS:
            res = []
            for it in range(N):
                lm = draw(rng, pool_t, w, heat_cv)
                res.append(simulate(w, lm, zfix, design))
            ok = [r for r in res if r.get("solved")]
            unsolved = [r for r in res if not r.get("solved")]
            # served probability is over ALL drawn realizations, not only the
            # ones that solved: an unsolved draw counts against reliability
            feas = [r for r in ok if r["feasible"]]
            mins = sorted(r["min_reserve_kWh"] for r in ok)
            short = [r["shortfall_kWh"] for r in ok]
            out["levels"][key][w] = {
                "T": R.SCEN[w][0], "days": R.SCEN[w][1], "n": len(res),
                "n_solved": len(ok), "n_unsolved": len(unsolved),
                "unsolved_status": sorted({r.get("status")
                                           for r in unsolved}) or None,
                "p_all_trips_served": round(len(feas) / max(1, len(res)), 4),
                # common criterion across operating policies: did every block
                # stay above the hard SoC floor? Unsolved draws count as
                # failures. This is what makes reserve settings comparable.
                "p_soc_floor_ok": round(
                    sum(1 for r in ok if r["min_reserve_kWh"] is not None
                        and r["min_reserve_kWh"] >= -1e-3) / max(1, len(res)), 4),
                "reserve_setting_kWh": R.RESERVE_RETURN,
                "expected_shortfall_kWh": round(float(np.mean(short)), 3),
                "p95_shortfall_kWh": round(float(np.percentile(short, 95)), 3),
                "min_reserve_p05": round(mins[max(0, int(0.05 * len(mins)))], 2)
                if mins else None,
                "min_reserve_median": round(mins[len(mins) // 2], 2)
                if mins else None,
                "mean_blocks_infeasible": round(
                    float(np.mean([r["blocks_infeasible"] for r in ok])), 3),
            }
            print(key, w, out["levels"][key][w], flush=True)
            json.dump(out, open(OUT_FILE, "w"), indent=1)
        wt = sum(R.SCEN[w][1] for w in BANDS)
        lv = out["levels"][key]
        out["levels"][key]["winter_weighted"] = {
            "p_day_fully_served": round(sum(
                lv[w]["p_all_trips_served"] * R.SCEN[w][1] for w in BANDS) / wt, 4),
            "expected_shortfall_kWh_per_winter": round(sum(
                lv[w]["expected_shortfall_kWh"] * R.SCEN[w][1]
                for w in BANDS), 1)}
    out["minutes"] = round((time.time() - t0) / 60, 1)
    json.dump(out, open(OUT_FILE, "w"), indent=1)
    for key, lv in out["levels"].items():
        print(key, "winter-weighted:", lv["winter_weighted"], flush=True)
    print("reliability done in", out["minutes"], "min", flush=True)
