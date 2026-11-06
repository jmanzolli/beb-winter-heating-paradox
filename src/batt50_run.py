"""Post-campaign: add the batt_50 sensitivity to the v8 archive.

The v8 sweep is (150, 100, 300) CAD/kWh against a 205.5 base, and all three
keep the full 18-burner fleet, so nothing in it brackets the price at which
FFH retention stops being optimal. This run reaches below that sweep.

Solved at the campaign's default lam=100 like every other sensitivity, so the
delta is comparable with the rest of the supplementary sensitivity table
(which is referenced to policy_lam100).

Run: ROUTE_INPUTS=route52_inputs_v7.json CAMP_OUT=campaign_v8_results.json \
     python batt50_run.py
"""
import campaign_v5 as C

f, g = C.set_batt(50.0)
C.solve("batt_50", mods=f, unmods=g)
C._dump()
print("batt_50 recorded")
