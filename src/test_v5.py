"""
v5 pre-campaign unit checks (revision protocol Sections 1.3 and 6 subset).
Quick MIP solve (coarse gap), then structural and accounting assertions.
Run: ROUTE_INPUTS=route52_inputs_v5.json python3 test_v5.py
"""

import os
os.environ.setdefault("ROUTE_INPUTS", "route52_inputs_v5.json")

import route52_prototype as R

TOL = 1e-4
fails = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name, detail)
    if not cond:
        fails.append(name)


# --- static checks -----------------------------------------------------------
days = sum(R.SCEN[w][1] for w in R.SCEN)
check("weights_sum_365", days == 365, f"(={days})")
check("offseason_heatless", "offseason" in R.HEATLESS)
check("ffh_rated_12", abs(R.P_FFH_RATED - 12.0) < TOL)
check("el_rated_23", abs(R.P_ELH_RATED - 23.0) < TOL)

# preconditioning and depot-charging windows disjoint by construction
overlaps = 0
for b in range(R.N_BLOCKS):
    for t in R.PRE_STEPS[b]:
        if ("depot", t) in R.AVAIL[b]:
            overlaps += 1
check("pre_charge_windows_disjoint", overlaps == 0, f"(overlaps={overlaps})")

# --- quick solve -------------------------------------------------------------
m = R.build_model(carbon_price_t=100.0)
m.Params.OutputFlag = 0
m.Params.MIPGapAbs = 25000
m.Params.TimeLimit = 900
m.optimize()
check("solve_found", m.SolCount > 0, f"status={m.Status}")

h = m._handles
K = range(len(R.BUS_CLASSES))

# off-season: zero diesel, zero heat
soff = m._scen["offseason"]
check("offseason_diesel_zero", soff["D"].X < TOL)
check("offseason_heat_zero",
      sum(v.X for v in soff["qel"].values())
      + sum(v.X for v in soff["qff"].values()) < 1e-3)

for w in R.SCEN:
    s = m._scen[w]
    # heater rated outputs respected
    bad_el = bad_ff = 0
    for (b, i), v in s["qel"].items():
        dur = R.BLOCKS[b].trips[i].dur_h
        if v.X > dur * R.P_ELH_RATED + 1e-4:
            bad_el += 1
    for (b, i), v in s["qff"].items():
        dur = R.BLOCKS[b].trips[i].dur_h
        if v.X > dur * R.P_FFH_RATED + 1e-4:
            bad_ff += 1
    check(f"{w}_heater_limits", bad_el == 0 and bad_ff == 0,
          f"(el={bad_el}, ffh={bad_ff})")
    # one class per block; plugs vs installed
    onec = all(abs(sum(s["z"][b, k].X for k in K) - 1) < 1e-4
               for b in range(R.N_BLOCKS))
    check(f"{w}_one_class_per_block", onec)
    # no bus on two plugs in one step (charging incl. precond)
    dbl = 0
    for b in range(R.N_BLOCKS):
        for t in R.STEPS:
            occ = sum(s["u"][b, n, t].X for n in R.SITES
                      if (b, n, t) in s["u"])
            occ += s["upre"][b, t].X if (b, t) in s["upre"] else 0.0
            if occ > 1 + 1e-4:
                dbl += 1
    check(f"{w}_single_plug_per_bus", dbl == 0, f"(violations={dbl})")
    # SoC window + energy closure
    viol = 0
    for b in range(R.N_BLOCKS):
        capw = R.DERATE[w][0] * sum(R.BUS_CLASSES[k].batt_nom * s["z"][b, k].X
                                    for k in K)
        nt = len(R.BLOCKS[b].trips)
        for i in range(nt):
            if s["Earr"][b, i].X < R.S_LO * capw - 1e-3:
                viol += 1
            if s["Edep"][b, i].X > R.S_UP * capw + 1e-3:
                viol += 1
    check(f"{w}_soc_window", viol == 0, f"(violations={viol})")
    # C1: preconditioning power respects the electric heater rating
    pk = max((v.X for v in s["ppre"].values()), default=0.0)
    check(f"{w}_precond_heater_rating", pk <= R.P_ELH_RATED + 1e-4,
          f"(peak={pk:.2f} kW vs {R.P_ELH_RATED} kW)")
    # C2: credited preconditioning heat <= delivered heat, and the delivered
    # heat respects the cabin storage cap
    bad_cr = bad_cap = 0
    for b in range(R.N_BLOCKS):
        blk = R.BLOCKS[b]
        e = sum(R.DT * s["ppre"][b, t].X for t in R.PRE_STEPS[b]
                if (b, t) in s["ppre"])
        cr = sum(R.DT * R.precond_chi(blk, t) * s["ppre"][b, t].X
                 for t in R.PRE_STEPS[b] if (b, t) in s["ppre"])
        if cr > e + 1e-6:
            bad_cr += 1
        if e > R.PRECOND_MAX_KWH + 1e-4:
            bad_cap += 1
    check(f"{w}_precond_credit_le_delivered", bad_cr == 0, f"({bad_cr})")
    check(f"{w}_precond_energy_cap", bad_cap == 0, f"({bad_cap})")

# purchased buses cover assignments (per class)
for k in K:
    used = max(sum(m._scen[w]["z"][b, k].X for b in range(R.N_BLOCKS))
               for w in R.SCEN)
    if used > h["x"][k].X + 1e-4:
        fails.append("fleet_cover")
check("fleet_cover", "fleet_cover" not in fails)

# cost identity: components sum to objective (obj includes carbon at lam=100)
from campaign_v5 import cost_parts
cp = cost_parts(m, 100.0)
recon = cp["F1"] + cp["carbon_cost"]
check("cost_identity", abs(recon - m.ObjVal) < 1.0,
      f"(recon={recon:.1f} vs obj={m.ObjVal:.1f})")

print()
print("FAILURES:", fails if fails else "none")
raise SystemExit(1 if fails else 0)
