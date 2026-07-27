"""
Route 52 sensitivity block, runnable as independent subsets.

campaign_v5.py runs the whole campaign in one sequential process, which is
right on a laptop but wastes a many-core host: the sensitivity runs are
independent solves that differ only in one parameter, so they can run as
concurrent processes. Each process writes its own shard (CAMP_OUT); merge
with merge_campaign.py afterwards.

  python3 sens_v6.py --list
  CAMP_OUT=sh_a.json python3 sens_v6.py cost      # ffh_om, grid, batt, capex
  CAMP_OUT=sh_b.json python3 sens_v6.py physical  # derate, reserve, tau
  CAMP_OUT=sh_c.json python3 sens_v6.py ops       # spare, n_minus_1, frozen_z

Every run is skipped if its label is already present in CAMP_OUT, so a
re-launch resumes rather than recomputes.

Usage: ROUTE_INPUTS=route52_inputs_v5.json CAMP_THREADS=16 \
       CAMP_OUT=shard.json python3 sens_v6.py <group> [<group> ...]
"""

import os
import sys
import time

os.environ.setdefault("ROUTE_INPUTS", "route52_inputs_v5.json")

import campaign_v5 as C
import route52_prototype as R


def _run_om(v):
    f, g = C.set_om(v)
    return C.solve(f"ffh_om_{int(v)}", mods=f, unmods=g)


def _run_grid(v):
    f, g = C.set_grid(v)
    return C.solve(f"grid_{int(v)}", mods=f, unmods=g)


def _run_batt(v):
    f, g = C.set_batt(v)
    return C.solve(f"batt_{int(v)}", mods=f, unmods=g)


def _run_capex(v):
    f, g = C.set_ffh_capex(v)
    return C.solve(f"ffh_capex_{int(v)}", mods=f, unmods=g)


def _run_derate(tag, cs, as_):
    f, g = C.set_derate(cs, as_)
    return C.solve(tag, mods=f, unmods=g)


def _run_reserve(v):
    f, g = C.set_reserve(v)
    return C.solve(f"reserve_{int(v)}", mods=f, unmods=g)


def _run_tau(v):
    f, g = C.set_tau(v)
    return C.solve(f"precond_tau_{v}", mods=f, unmods=g)


def _run_spare(v):
    return C.solve(f"spare_{int(v * 100)}", lam=100.0, spare=v)


def _run_frozen():
    return C.solve("frozen_z", lam=100.0, freeze_z=True)


def _run_nminus1():
    """N-1 depot charger on the recorded carbon-price design."""
    rec = {r["label"]: r for r in C.OUT["runs"]}.get("policy_lam100")
    if rec is None:
        print("n_minus_1 needs policy_lam100 in the shard; skipping",
              flush=True)
        return None, None
    d = C.design_from_record(rec)
    for (n, p), v in list(d["wch"].items()):
        if n == "depot" and v > 0:
            d["wch"][(n, p)] = v - 1
            break
    return C.solve("n_minus_1", lam=100.0, fix_design=d)


GROUPS = {
    "cost": [lambda: _run_om(500.0), lambda: _run_om(2000.0),
             lambda: _run_grid(100.0), lambda: _run_grid(300.0),
             lambda: _run_batt(100.0), lambda: _run_batt(50.0),
             lambda: _run_capex(5000.0), lambda: _run_capex(15000.0)],
    "physical": [lambda: _run_derate("derate_mild", 0.002, 0.004),
                 lambda: _run_derate("derate_harsh", 0.006, 0.012),
                 lambda: _run_reserve(25.0), lambda: _run_reserve(50.0),
                 lambda: _run_tau(0.25), lambda: _run_tau(1.0)],
    "ops": [lambda: _run_spare(0.15), _run_frozen, _run_nminus1],
}


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if "--list" in sys.argv or not args:
        for g, fns in GROUPS.items():
            print(f"{g:<10} {len(fns)} runs")
        raise SystemExit(0)
    t0 = time.time()
    print(f"host {C._HOST} | threads {C.THREADS} | out {C.OUT_FILE} | "
          f"groups {args}", flush=True)
    for g in args:
        if g not in GROUPS:
            print(f"unknown group {g}; known: {list(GROUPS)}")
            continue
        for fn in GROUPS[g]:
            fn()
    C.OUT["meta"]["total_minutes"] = round((time.time() - t0) / 60, 1)
    C._dump()
    print("sensitivities done in", C.OUT["meta"]["total_minutes"], "min",
          flush=True)
