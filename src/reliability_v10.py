"""
Out-of-sample reliability, protocol v10 (review of 2026-11-09, items M2-M4).

Evaluates a FIXED first-stage design (and its day-ahead block-class
assignment, recovered from the planning model) against realized days. Changes
from reliability_v5.py:

  M4(i)   traction residuals are band-conditional: log r = mu_band + f + e,
          with mu_band the band mean of the Route 52 bus-day residuals
          (bands with < 30 bus-days borrow the mean below -5 C)
  M4(ii)  the day's temperature is drawn from the ECCC daily means of that
          band (24 winters), not fixed at the representative temperature;
          heating demand, useful-heat fraction and cold derates follow it
  M4(iii) a day-level factor f, drawn once per day and shared by every
          block, carries the between-date part of the traction residual;
          e is the within-date (block-level) part
  M4(iv)  heat level "data": block-level heat-demand dispersion implied by
          the companion model's residual scale (sigma = 1.66 kW on the
          trip-averaged rate), CV_b = sigma / mean planning rate of block b
          at the drawn temperature; "cvX" keeps a declared stress level
  M2      three outcomes per realized day, measured separately:
            reserve-compliant  every block stays above the 10% SoC floor and
                               returns with the 10 kWh end-of-day reserve
                               (energy slack < 0.1 kWh); the previous
                               "fully served" metric
            trips completed    on days that are not reserve-compliant, the
                               day is re-dispatched with the floor lowered to
                               a hard cut-off (REL_HARD_FLOOR, default 5% SoC)
                               and no end-of-day reserve; a trip is lost if
                               the bus arrives below the cut-off
            comfort met        cabin heat may go unmet at a high penalty
                               (soft_heat), so heat above the heater ratings
                               is recorded as a comfort shortfall instead of
                               an unsolved draw

Recourse objective: elastic energy slack + 1000 x unmet cabin heat, solved to
an absolute tolerance of 1e-3 (slack-only, as in the 2026-11-06 revision).

Env:
  REL_RESULTS, REL_DESIGN   archive file and run label of the design
  REL_INPUTS                rel_inputs_v10.json (prep_reliability_v10.py)
  REL_WINTERS               eccc_winter_bands_v9.json (24-winter band counts)
  REL_LEVELS                comma list of trac | trac_fixT | data | cv<x>
                            (trac_fixT: new traction, temperature fixed at
                            the band representative, for attribution)
  REL_OUT, REL_SEED, REL_LAM (0), REL_HARD_FLOOR (0.05), REL_THREADS (2)
  REL_ASSIGN                day-ahead block-class assignment:
                              plan      from the cost-minimising planning solve
                                        (default; the first v10 runs). That
                                        solve is cost-indifferent between many
                                        assignments, so in a mixed fleet the
                                        scarce bus classes land on arbitrary
                                        blocks
                              hedged    per band, the assignment that tolerates
                                        the largest uniform rise in traction
                                        energy on a cold day of the band (10th
                                        percentile of its daily means); see
                                        hedged_assignment
                              <file>    read an assignment written by the
                                        "assign" mode
  REL_CHUNK                 "i/n": simulate only the draws with index % n == i.
                            Every draw is still generated, so the chunks of one
                            level share the random stream and together equal an
                            unchunked run. Combine with the "merge" mode.
Usage: python reliability_v10.py [N_per_band]
       python reliability_v10.py assign OUT.json
       python reliability_v10.py merge OUT.json SHARD.json [SHARD.json ...]
"""
import json
import os
import sys
import time

import numpy as np

import route52_prototype as R
from campaign_v5 import design_from_record

RESULTS = os.environ["REL_RESULTS"]
DESIGN_LABEL = os.environ["REL_DESIGN"]
OUT_FILE = os.environ.get("REL_OUT", f"rel_v10_{DESIGN_LABEL}.json")
RELIN = json.load(open(os.environ.get("REL_INPUTS", "rel_inputs_v10.json")))
WINTERS = json.load(open(os.environ.get("REL_WINTERS",
                                        "eccc_winter_bands_v9.json")))["winters"]
LEVELS = os.environ.get("REL_LEVELS", "trac,data,cv0.20").split(",")
REL_LAM = float(os.environ.get("REL_LAM", 0.0))
SEED = int(os.environ.get("REL_SEED", 20261109))
HARD_FLOOR = float(os.environ.get("REL_HARD_FLOOR", 0.05))
THREADS = int(os.environ.get("REL_THREADS", 2))
ASSIGN = os.environ.get("REL_ASSIGN", "plan")
CHUNK_I, CHUNK_N = (int(v) for v in os.environ.get("REL_CHUNK", "0/1").split("/"))
HEDGE_T_PCT = 10.0          # cold day of the band used for the hedged assignment
HEDGE_KAPPA = (0.6, 2.0)    # search range of the uniform traction multiplier
HEDGE_STEPS = 8             # bisection steps (resolution about 0.005)
HEDGE_TLIM = float(os.environ.get("REL_HEDGE_TLIM", 60))   # s per trial solve
COMFORT_PEN = 1000.0
FAIL_KWH = 0.1
BANDS = [w for w in R.SCEN if w not in R.HEATLESS]
TR = RELIN["traction"]
F_DATE = np.asarray(TR["f_date"])
WITHIN = np.asarray(TR["within"])
TEMPS = {w: np.asarray(v) for w, v in RELIN["temps"].items()}
SIGMA_HEAT = RELIN["heat"]["sigma_kW"]


# ------------------------------------------------------------------ draws
def block_rate(b, T):
    """Time-weighted mean planning heat rate (kW) of block b at T."""
    trips = R.BLOCKS[b].trips
    num = sum(R.q_heat_rate(T, tr.f_stop, tr.speed) * tr.dur_h for tr in trips)
    return R.HEAT_DEMAND_MULT * num / max(1e-9, sum(tr.dur_h for tr in trips))


def draw(rng, w, level):
    """One realized day of band w: temperature, then per-block multipliers."""
    T = (R.SCEN[w][0] if level == "trac_fixT"
         else float(TEMPS[w][rng.integers(len(TEMPS[w]))]))
    f = float(F_DATE[rng.integers(len(F_DATE))])
    mu = TR["mu_log_ratio"][w]
    lm, cvs = {}, []
    for b in range(R.N_BLOCKS):
        tm = float(np.exp(mu + f + WITHIN[rng.integers(len(WITHIN))]))
        if level == "data":
            q = block_rate(b, T)
            cv = SIGMA_HEAT / q if q > 1e-6 else 0.0
        elif level.startswith("cv"):
            cv = float(level[2:])
        else:
            cv = 0.0
        cvs.append(cv)
        if cv > 0:
            sig = np.sqrt(np.log(1.0 + cv ** 2))
            hm = float(np.exp(rng.normal(-0.5 * sig ** 2, sig)))
        else:
            hm = 1.0
        for i in range(len(R.BLOCKS[b].trips)):
            lm[(w, b, i)] = (tm, hm)
    return T, f, lm, float(np.mean(cvs))


# --------------------------------------------------------------- harness
def fix_first_stage(m, design):
    h = m._handles
    for k in range(len(R.BUS_CLASSES)):
        m.addConstr(h["x"][k] == design["x"][k])
    for n in R.SITES:
        for p in R.CH_CLASSES:
            m.addConstr(h["wch"][n, p] == design["wch"][(n, p)])
            m.addConstr(h["ysite"][n, p] == design["ysite"][(n, p)])
        for j in range(len(R.GRID_TIERS)):
            m.addConstr(h["ygrid"][n, j] == design["ygrid"][(n, j)])


def planning_solution(design):
    """Day-ahead block-class assignment of the design, per band, at the band
    representative temperature (what the planner would schedule)."""
    m = R.build_model(carbon_price_t=REL_LAM)
    fix_first_stage(m, design)
    m.Params.OutputFlag = 0
    m.Params.MIPGapAbs = 500
    m.Params.TimeLimit = 1200
    m.Params.Threads = THREADS
    m.optimize()
    assert m.SolCount > 0, "could not recover planning assignment"
    return {w: {b: max(range(len(R.BUS_CLASSES)), key=lambda k: m._scen[w]["z"][b, k].X)
                for b in range(R.N_BLOCKS)} for w in R.SCEN}


def hedged_assignment(design):
    """Day-ahead block-class assignment per band that tolerates the largest
    uniform rise in traction energy.

    For band w the day is set to a cold day of the band (HEDGE_T_PCT percentile
    of its ECCC daily means) and every trip's traction energy is multiplied by
    kappa. The assignment is free; the day passes if the least energy slack is
    below FAIL_KWH. Bisection finds the largest kappa that passes, and the
    assignment of that solve is kept. A trial stops at the first passing
    incumbent or after HEDGE_TLIM seconds; a trial that times out without one
    counts as failing, so the tolerated kappa is a lower estimate. The within-date traction residual is
    independent across blocks, so a uniform multiplier is the hedge that does
    not presume which block will be hit. If no kappa in the range passes, the
    assignment with the least slack at the band-mean multiplier is used.

    Returns (zfix, info): zfix = {w: {b: k}} for the heated bands, info the
    kappa, temperature and class per block of each band.
    """
    K = range(len(R.BUS_CLASSES))
    zfix, info = {}, {}
    for w in BANDS:
        T = float(np.percentile(TEMPS[w], HEDGE_T_PCT))

        def trial(kappa):
            lm = {(w, b, i): (kappa, 1.0) for b in range(R.N_BLOCKS)
                  for i in range(len(R.BLOCKS[b].trips))}
            t = time.time()
            m, _ = solve_day(w, T, lm, {w: {}}, design, R.S_LO, R.RESERVE_RETURN,
                             tlim=HEDGE_TLIM, obj_stop=0.5 * FAIL_KWH)
            if m is None:
                print(f"  {w} kappa {kappa:.4f}: no solution, {time.time() - t:.0f} s",
                      flush=True)
                return None, None
            z = m._scen[w]["z"]
            a = {b: max(K, key=lambda k: z[b, k].X) for b in range(R.N_BLOCKS)}
            sv = float(m._shortfall.getValue())
            print(f"  {w} kappa {kappa:.4f}: slack {sv:.2f} kWh, {time.time() - t:.0f} s",
                  flush=True)
            return sv, a

        lo, hi = HEDGE_KAPPA
        s, a = trial(lo)
        if a is None or s >= FAIL_KWH:
            kappa = float(np.exp(TR["mu_log_ratio"][w]))
            s, a = trial(kappa)
            assert a is not None, f"no day-ahead assignment for band {w}"
            best, tol, note = a, None, "no multiplier in range passes; least slack at band mean"
        else:
            best, tol, note = a, lo, "bisection"
            s, a = trial(hi)
            if a is not None and s < FAIL_KWH:
                best, tol, note = a, hi, "passes at the upper end of the range"
            else:
                for _ in range(HEDGE_STEPS):
                    mid = 0.5 * (lo + hi)
                    s, a = trial(mid)
                    if a is not None and s < FAIL_KWH:
                        lo, best, tol = mid, a, mid
                    else:
                        hi = mid
        zfix[w] = best
        info[w] = {"T": round(T, 2), "kappa_tolerated": None if tol is None else round(tol, 4),
                   "note": note,
                   "class_of_block": {str(b): R.BUS_CLASSES[k].name for b, k in best.items()}}
        print("hedged", w, "T", round(T, 2), "kappa", info[w]["kappa_tolerated"], note,
              flush=True)
    return zfix, info


def load_assignment(path, design_label):
    d = json.load(open(path))
    assert d["design_label"] == design_label, (d["design_label"], design_label)
    return ({w: {int(b): k for b, k in v.items()} for w, v in d["zfix"].items()},
            {"mode": d["mode"], "file": os.path.basename(path), "bands": d["bands"]})


def solve_day(w, T, lm, zfix, design, s_lo, reserve, tlim=300, obj_stop=None):
    """Re-dispatch one realized day; returns the solved model or None."""
    sc0, dr0, slo0, res0 = R.SCEN[w], R.DERATE[w], R.S_LO, R.RESERVE_RETURN
    R.SCEN[w] = (T, sc0[1])
    if not R.INP.get("derates", {}).get(w):
        R.DERATE[w] = R._derates(T)
    R.S_LO, R.RESERVE_RETURN = s_lo, reserve
    try:
        m = R.build_model(carbon_price_t=REL_LAM, load_mult=lm, elastic=True,
                          only_scen=w, soft_heat=True, heat_penalty=COMFORT_PEN)
        fix_first_stage(m, design)
        z = m._scen[w]["z"]
        for b, k in zfix[w].items():
            m.addConstr(z[b, k] == 1)
        m.setObjective(m._shortfall + COMFORT_PEN * m._heat_short)
        m.Params.OutputFlag = 0
        m.Params.MIPGap = 0.0
        m.Params.MIPGapAbs = 1e-3
        m.Params.TimeLimit = tlim
        if obj_stop is not None:
            m.Params.BestObjStop = obj_stop
        m.Params.Threads = THREADS
        m.optimize()
        cap = {b: R.DERATE[w][0] * sum(R.BUS_CLASSES[k].batt_nom * m._scen[w]["z"][b, k].X
                                       for k in range(len(R.BUS_CLASSES)))
               for b in range(R.N_BLOCKS)} if m.SolCount else None
        return (m if m.SolCount else None), cap
    finally:
        R.SCEN[w], R.DERATE[w], R.S_LO, R.RESERVE_RETURN = sc0, dr0, slo0, res0


def _vsum(m, prefix):
    return float(sum(v.X for v in m.getVars() if v.VarName.startswith(prefix)))


def simulate(w, T, lm, zfix, design):
    days = R.SCEN[w][1]
    m, cap = solve_day(w, T, lm, zfix, design, R.S_LO, R.RESERVE_RETURN)
    if m is None:
        return {"solved": False}
    s = m._scen[w]
    short = float(m._shortfall.getValue()) if hasattr(m._shortfall, "getValue") else 0.0
    heat_short = float(m._heat_short.getValue()) / days if hasattr(
        m._heat_short, "getValue") else 0.0
    margins = [min(s["Earr"][b, i].X - R.S_LO * cap[b]
                   for i in range(len(R.BLOCKS[b].trips))) for b in range(R.N_BLOCKS)]
    r = {"solved": True, "T": round(T, 1),
         "shortfall_kWh": round(short, 3),
         "slack_floor_kWh": round(_vsum(m, f"slack_{w}_"), 3),
         "slack_reserve_kWh": round(_vsum(m, f"slackret_{w}_"), 3),
         "slack_closure_kWh": round(_vsum(m, f"slackcyc_{w}_"), 3),
         "reserve_ok": short < FAIL_KWH,
         "heat_short_kWh": round(heat_short, 3),
         "comfort_ok": heat_short < FAIL_KWH,
         "min_reserve_kWh": round(float(min(margins)), 2),
         "blocks_reserve_fail": int(sum(1 for x in margins if x < -1e-3)),
         "trips_lost": 0, "blocks_with_lost_trip": 0, "next_day_deficit_kWh": 0.0}
    if not r["reserve_ok"]:
        # physical service: dip into the reserve down to the hard cut-off
        m2, _ = solve_day(w, T, lm, zfix, design, HARD_FLOOR, 0.0)
        if m2 is None:
            r["trips_lost"] = None
        else:
            lost, blocks = 0, set()
            for v in m2.getVars():
                nm = v.VarName
                if nm.startswith(f"slack_{w}_") and v.X > FAIL_KWH:
                    lost += 1
                    blocks.add(nm.split("[")[0])
            r["trips_lost"] = lost
            r["blocks_with_lost_trip"] = len(blocks)
            r["next_day_deficit_kWh"] = round(_vsum(m2, f"slackcyc_{w}_"), 3)
    return r


def summarize(res, w, n_trips):
    ok = [r for r in res if r.get("solved")]
    n = len(res)
    fails = [r for r in ok if not r["reserve_ok"]]
    lost = [r["trips_lost"] for r in ok if r["trips_lost"] is not None]
    mins = sorted(r["min_reserve_kWh"] for r in ok)
    short = [r["shortfall_kWh"] for r in ok]
    return {
        "T_rep": R.SCEN[w][0], "days": R.SCEN[w][1], "n": n, "n_solved": len(ok),
        "T_drawn_mean": round(float(np.mean([r["T"] for r in ok])), 2) if ok else None,
        "p_reserve_compliant": round(sum(r["reserve_ok"] for r in ok) / max(1, n), 4),
        "p_trips_completed": round(sum(1 for r in ok if r["trips_lost"] == 0) / max(1, n), 4),
        "p_comfort_met": round(sum(r["comfort_ok"] for r in ok) / max(1, n), 4),
        "p_reserve_and_comfort": round(sum(r["reserve_ok"] and r["comfort_ok"]
                                           for r in ok) / max(1, n), 4),
        "mean_trips_lost": round(float(np.mean(lost)), 4) if lost else 0.0,
        "share_trips_lost": round(float(np.mean(lost)) / n_trips, 6) if lost else 0.0,
        "mean_trips_lost_given_fail": round(float(np.mean(
            [r["trips_lost"] for r in fails if r["trips_lost"] is not None])), 3)
        if fails else 0.0,
        "expected_shortfall_kWh": round(float(np.mean(short)), 3) if ok else None,
        "p95_shortfall_kWh": round(float(np.percentile(short, 95)), 3) if ok else None,
        "shortfall_given_fail_mean_kWh": round(float(np.mean(
            [r["shortfall_kWh"] for r in fails])), 3) if fails else 0.0,
        "slack_split_mean_kWh": {k: round(float(np.mean([r[f"slack_{k}_kWh"] for r in ok])), 3)
                                 for k in ("floor", "reserve", "closure")} if ok else None,
        "min_reserve_p05": round(mins[max(0, int(0.05 * len(mins)))], 2) if mins else None,
        "min_reserve_median": round(mins[len(mins) // 2], 2) if mins else None,
        "mean_heat_short_kWh_day": round(float(np.mean([r["heat_short_kWh"] for r in ok])), 3)
        if ok else None,
        "mean_next_day_deficit_kWh": round(float(np.mean(
            [r["next_day_deficit_kWh"] for r in ok])), 3) if ok else None,
    }


def winter_rollup(lv, n_trips):
    wt = sum(R.SCEN[w][1] for w in BANDS)
    breach = {w: (1 - lv[w]["p_reserve_compliant"]) for w in BANDS}
    trip_fail = {w: (1 - lv[w]["p_trips_completed"]) for w in BANDS}
    hist = {}
    for name, c in WINTERS.items():
        hist[name] = {"reserve_breach_days": round(sum(breach[w] * c[w] for w in BANDS), 3),
                      "trip_loss_days": round(sum(trip_fail[w] * c[w] for w in BANDS), 3),
                      "trips_lost": round(sum(lv[w]["mean_trips_lost"] * c[w]
                                              for w in BANDS), 2)}
    def ext(key):
        vals = [h[key] for h in hist.values()]
        worst = max(hist, key=lambda k: hist[k][key])
        return {"mean": round(float(np.mean(vals)), 3), "max": round(max(vals), 3),
                "worst_winter": worst}
    return {
        "p_day_reserve_compliant": round(sum(lv[w]["p_reserve_compliant"] * R.SCEN[w][1]
                                             for w in BANDS) / wt, 5),
        "p_day_trips_completed": round(sum(lv[w]["p_trips_completed"] * R.SCEN[w][1]
                                           for w in BANDS) / wt, 5),
        "p_day_comfort_met": round(sum(lv[w]["p_comfort_met"] * R.SCEN[w][1]
                                       for w in BANDS) / wt, 5),
        "reserve_breach_days_per_winter": round(sum(breach[w] * R.SCEN[w][1]
                                                    for w in BANDS), 3),
        "trip_loss_days_per_winter": round(sum(trip_fail[w] * R.SCEN[w][1]
                                               for w in BANDS), 3),
        "trips_lost_per_winter": round(sum(lv[w]["mean_trips_lost"] * R.SCEN[w][1]
                                           for w in BANDS), 2),
        "share_winter_trips_lost": round(sum(lv[w]["mean_trips_lost"] * R.SCEN[w][1]
                                             for w in BANDS) / (n_trips * wt), 7),
        "expected_shortfall_kWh_per_winter": round(sum(
            lv[w]["expected_shortfall_kWh"] * R.SCEN[w][1] for w in BANDS), 1),
        "historical_24_winters": {k: ext(k) for k in
                                  ("reserve_breach_days", "trip_loss_days", "trips_lost")},
    }


def finish(out, raw, n_trips):
    """Band summaries and winter rollup of every level from the per-draw results."""
    for level, by_band in raw.items():
        lv = out["levels"].setdefault(level, {})
        for w, res in by_band.items():
            lv[w] = summarize(res, w, n_trips)
            lv[w]["heat_cv_mean"] = round(float(np.mean(
                [r["heat_cv_mean"] for r in res])), 3)
        if all(w in lv for w in BANDS):
            lv["winter_weighted"] = winter_rollup(lv, n_trips)


if __name__ == "__main__":
    rec = {r["label"]: r for r in json.load(open(RESULTS))["runs"]}[DESIGN_LABEL]
    design = design_from_record(rec)
    n_trips = sum(len(blk.trips) for blk in R.BLOCKS)

    if len(sys.argv) > 1 and sys.argv[1] == "assign":
        t0 = time.time()
        zfix, bands = hedged_assignment(design)
        json.dump({"design_label": DESIGN_LABEL, "mode": "hedged",
                   "T_percentile": HEDGE_T_PCT, "kappa_range": HEDGE_KAPPA,
                   "zfix": {w: {str(b): k for b, k in v.items()} for w, v in zfix.items()},
                   "bands": bands, "minutes": round((time.time() - t0) / 60, 1)},
                  open(sys.argv[2], "w"), indent=1)
        print("assignment written to", sys.argv[2], flush=True)
        sys.exit(0)

    if len(sys.argv) > 1 and sys.argv[1] == "merge":
        shards = [json.load(open(f)) for f in sys.argv[3:]]
        out = {k: v for k, v in shards[0].items() if k not in ("raw", "levels", "chunk",
                                                               "minutes")}
        for sh in shards:
            for k in ("design_label", "n_per_band", "seed", "assignment"):
                assert sh[k] == out[k], f"shards differ in {k}"
        assert sorted(sh["chunk"][0] for sh in shards) == list(range(shards[0]["chunk"][1])), \
            "chunks missing or repeated"
        raw = {}
        for level in shards[0]["raw"]:
            raw[level] = {}
            for w in BANDS:
                res = sorted((r for sh in shards for r in sh["raw"][level].get(w, [])),
                             key=lambda r: r["i"])
                assert [r["i"] for r in res] == list(range(out["n_per_band"])), \
                    f"{level} {w}: {len(res)} draws, expected {out['n_per_band']}"
                raw[level][w] = res
        out["levels"] = {}
        finish(out, raw, n_trips)
        out["minutes"] = round(sum(sh.get("minutes", 0) for sh in shards), 1)
        out["merged_from"] = len(shards)
        json.dump(out, open(sys.argv[2], "w"), indent=1)
        for level, lv in out["levels"].items():
            print(level, "winter:", lv.get("winter_weighted"), flush=True)
        sys.exit(0)

    N = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    t0 = time.time()
    print("design", DESIGN_LABEL, rec["fleet"], rec["chargers"], flush=True)
    if ASSIGN == "plan":
        zfix, assignment = planning_solution(design), {"mode": "plan"}
    elif ASSIGN == "hedged":
        zfix, bands = hedged_assignment(design)
        assignment = {"mode": "hedged", "bands": bands}
    else:
        zfix, assignment = load_assignment(ASSIGN, DESIGN_LABEL)
    chunked = CHUNK_N > 1
    out = {"protocol": "v10", "design_label": DESIGN_LABEL, "design": rec["fleet"],
           "chargers": rec["chargers"], "n_per_band": N, "seed": SEED,
           "hard_floor_soc": HARD_FLOOR, "n_trips_per_day": n_trips,
           "assignment": assignment,
           "traction": {k: v for k, v in TR.items() if k not in ("f_date", "within")},
           "temps_note": RELIN["temps_note"], "heat": RELIN["heat"], "levels": {}}
    if chunked:
        out["chunk"] = [CHUNK_I, CHUNK_N]
        out["raw"] = {}
    raw = {}
    for li, level in enumerate(LEVELS):
        rng = np.random.default_rng(SEED + li)   # common draws across designs
        raw[level] = {}
        for w in BANDS:
            res = []
            for j in range(N):
                T, f, lm, cv = draw(rng, w, level)
                if j % CHUNK_N != CHUNK_I:
                    continue                      # drawn, simulated by another chunk
                r = simulate(w, T, lm, zfix, design)
                r["i"] = j
                r["heat_cv_mean"] = round(cv, 3)
                res.append(r)
            raw[level][w] = res
            finish(out, {level: {w: res}}, n_trips)
            if chunked:
                out["raw"] = raw
            print(level, w, out["levels"][level][w], flush=True)
            json.dump(out, open(OUT_FILE, "w"), indent=1)
        finish(out, {level: raw[level]}, n_trips)
        print(level, "winter:", out["levels"][level]["winter_weighted"], flush=True)
    out["minutes"] = round((time.time() - t0) / 60, 1)
    json.dump(out, open(OUT_FILE, "w"), indent=1)
    print("done in", out["minutes"], "min", flush=True)
