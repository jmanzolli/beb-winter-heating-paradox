"""Stage A of the reliability-matched premium: FFH-free designs at raised
planning reserve.

The reported +48.8 kCAD/yr premium for full heating electrification compares
two designs that are not equally reliable. Out of sample they are
indistinguishable on the state-of-charge floor (99.85 against 99.84% of winter
days) but not on the end-of-day reserve, 99.62 against 90.26%, and in the
severe band 95.7 against 37.7%. The premium is therefore the cost of removing
the burners, not the cost of removing them at unchanged operating margin.

This sweeps the planning reserve Gamma used when the FFH-free design is
selected. A larger Gamma makes the first stage buy the battery and charging
capacity needed to finish the day with more in hand, so cost rises and
out-of-sample reserve compliance improves. Stage B then evaluates each design
in the reliability harness at the STANDARD 10 kWh judging requirement -- not
at its own Gamma, which would measure a different thing -- so the resulting
compliance is directly comparable with the baseline's 99.62%.

Run: ROUTE_INPUTS=route52_inputs_v7.json CAMP_OUT=relmatch_v8.json \
     python relmatch_run.py
"""
import os

os.environ.setdefault("ROUTE_INPUTS", "route52_inputs_v7.json")
os.environ.setdefault("CAMP_OUT", "relmatch_v8.json")

import campaign_v5 as C

GAMMAS = [float(g) for g in
          os.environ.get("RELMATCH_GAMMAS", "25,50,75,100").split(",")]

for g in GAMMAS:
    label = f"relmatch_eps0_r{int(g)}"
    if label in C.DONE:
        print(f"{label} -> already recorded", flush=True)
        continue
    f, u = C.set_reserve(g)
    C.solve(label, eps=0.0, lam=0.0, mods=f, unmods=u, tlim=C.TLIM)

C.dedup_runs()
print("\nreserve sweep complete")
for r in C.OUT["runs"]:
    if r["label"].startswith("relmatch_"):
        print(f"  {r['label']}: F1 {r['F1']:,.1f} gap {r.get('abs_gap', 0):,.0f} "
              f"fleet {r['fleet']} chargers {r['chargers']}")
