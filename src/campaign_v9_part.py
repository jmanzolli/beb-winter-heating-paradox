"""Run one part of the Route 52 campaign so the parts can run in parallel.

Same solves, labels and settings as campaign_v5.py's main block, split into
independent shards (each with its own CAMP_OUT); merge them afterwards with
merge_campaign.py. Parts:
  core   baselines, lexicographic frontier, carbon-price sweep, breakpoints,
         refinement pass and baseline-monotonicity re-solve   (main A,B,C,H,H2)
  bench  mean-temperature benchmark, frozen assignment, N-1   (main D,E,F)
         (re-solves policy_lam100 for the N-1 design; the merge keeps the
         tighter of the two records)
  sensA  FFH O&M, grid cost, battery price, cold derates      (main G, part 1)
  sensB  reserve, spare ratio, preconditioning tau, FFH capex (main G, part 2)

Run: ROUTE_INPUTS=route52_inputs_v9.json CAMP_OUT=sh_core.json \
     python campaign_v9_part.py core
"""
import re
import sys
import time

import campaign_v5 as C

part = sys.argv[1]
t0 = time.time()
print("=== campaign part", part, flush=True)

if part == "core":
    econ, m0 = C.solve("econ_lam0", lam=0.0)
    pol, m100 = C.solve("policy_lam100", lam=100.0)
    d100 = C.design_of(m100) if m100 is not None else C.design_from_record(pol)
    if "ops_metrics_policy" not in C.OUT:
        _, m100 = C.solve("policy_lam100_ops", lam=100.0, fix_design=d100,
                          tlim=900, force=True)
        C.OUT["ops_metrics_policy"] = C.ops_metrics(m100)
    C._dump()
    co2max = econ["co2_t"]
    frontier = []
    for frac in (1.0, 0.7, 0.5, 0.35, 0.2, 0.1, 0.0):
        rec, mm = C.solve(f"eps_{frac:.2f}", eps=co2max * frac, lam=0.0,
                          lexicographic=True, tlim=C.TLIM_HARD)
        if rec:
            frontier.append(rec)
    C.OUT["frontier_labels"] = [r["label"] for r in frontier]
    C._dump()
    for lamv in (200, 500, 1000, 2000, 3500, 5000, 10000):
        C.solve(f"lam_{lamv}", lam=float(lamv),
                tlim=C.TLIM_HARD if lamv in (3500, 10000) else C.TLIM)
    fr = sorted(frontier, key=lambda r: -r["co2_t"])
    bps = []
    for a, b in zip(fr, fr[1:]):
        dc, de = b["F1"] - a["F1"], a["co2_t"] - b["co2_t"]
        if de > 1e-3 and dc > 0:
            bps.append(round(dc / de, 0))
    C.OUT["breakpoint_prices"] = sorted(set(bps))
    for lamv in sorted(set(bps))[:3]:
        C.solve(f"bp_lam_{int(lamv)}", lam=float(lamv), tlim=C.TLIM)
    C._dump()
    # refinement pass (H)
    recs = {r["label"]: r for r in C.OUT["runs"]}
    loose = [lb for lb in C.OUT.get("frontier_labels", [])
             if recs.get(lb, {}).get("abs_gap", 0) > C.ABS_GAP]
    print("refinement targets:", loose, flush=True)
    for lb in loose:
        r0 = recs[lb]
        C.solve(lb, eps=r0["eps"], lam=0.0, lexicographic=True,
                tlim=C.TLIM_HARD, force=True,
                mip_start=C.design_from_record(r0))
    # baseline monotonicity (H2)
    recs = {r["label"]: r for r in C.OUT["runs"]}
    b0 = recs.get("econ_lam0")
    if b0:
        cmp_ = re.compile(r"^(eps_|lam_|bp_lam_|policy_lam)")
        cheaper = [r for r in C.OUT["runs"] if cmp_.match(r["label"])
                   and r.get("F1", 9e18) < b0["F1"] - 1.0]
        if cheaper:
            best = min(cheaper, key=lambda r: r["F1"])
            print(f"baseline dominated by {best['label']}; re-solving", flush=True)
            C.solve("econ_lam0", lam=0.0, tlim=C.TLIM_HARD, force=True,
                    mip_start=C.design_from_record(best))

elif part == "bench":
    pol, m100 = C.solve("policy_lam100", lam=100.0)
    d100 = C.design_of(m100) if m100 is not None else C.design_from_record(pol)
    f, g = C.set_deterministic()
    det, mdet = C.solve("det_meanT", lam=100.0, mods=f, unmods=None)
    ddet = (C.design_of(mdet) if mdet is not None
            else (C.design_from_record(det) if det else None))
    g()
    if ddet:
        rec, _ = C.solve("det_design_full_test", lam=100.0, fix_design=ddet)
        C.OUT["det_feasible_full"] = rec is not None
    C._dump()
    C.solve("frozen_z", lam=100.0, freeze_z=True)
    dm = {k: dict(v) if isinstance(v, dict) else v for k, v in d100.items()}
    for (n, p), v in list(dm["wch"].items()):
        if n == "depot" and v > 0:
            dm["wch"][(n, p)] = v - 1
            break
    rec, _ = C.solve("n_minus_1", lam=100.0, fix_design=dm)
    C.OUT["n_minus_1_feasible"] = rec is not None

elif part == "sensA":
    for v in (500.0, 2000.0):
        f, g = C.set_om(v); C.solve(f"ffh_om_{int(v)}", mods=f, unmods=g)
    for gc in (100.0, 300.0):
        f, g = C.set_grid(gc); C.solve(f"grid_{int(gc)}", mods=f, unmods=g)
    for bp in (150.0, 100.0, 300.0):
        f, g = C.set_batt(bp); C.solve(f"batt_{int(bp)}", mods=f, unmods=g)
    for tag, cs, as_ in (("derate_mild", 0.002, 0.004),
                         ("derate_harsh", 0.006, 0.012)):
        f, g = C.set_derate(cs, as_); C.solve(tag, mods=f, unmods=g)

elif part == "sensB":
    for rv in (25.0, 50.0):
        f, g = C.set_reserve(rv); C.solve(f"reserve_{int(rv)}", mods=f, unmods=g)
    for sp in (0.15,):
        C.solve(f"spare_{int(sp*100)}", lam=100.0, spare=sp)
    for tv in (0.25, 1.0):
        f, g = C.set_tau(tv); C.solve(f"precond_tau_{tv}", mods=f, unmods=g)
    for fc in (5_000.0, 15_000.0):
        f, g = C.set_ffh_capex(fc)
        C.solve(f"ffh_capex_{int(fc)}", mods=f, unmods=g)

else:
    sys.exit(f"unknown part {part}")

C.dedup_runs()
C.OUT["meta"]["total_minutes"] = round((time.time() - t0) / 60, 1)
C._dump()
print("part", part, "done in", C.OUT["meta"]["total_minutes"], "min", flush=True)
