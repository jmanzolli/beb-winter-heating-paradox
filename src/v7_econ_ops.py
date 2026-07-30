"""Post-campaign: store ops_metrics for the ECONOMIC baseline (fix-design
recourse re-solve), so the manuscript's Fig. 3(b) margins and the ops
diagnostics can be reported for the same design as panels (a).
Run: ROUTE_INPUTS=route52_inputs_v7.json CAMP_OUT=campaign_v7_results.json"""
import campaign_v5 as C

rec = C.DONE.get("econ_lam0")
assert rec, "econ_lam0 not in results yet"
d = C.design_from_record(rec)
r, m = C.solve("econ_lam0_ops", lam=0.0, fix_design=d, tlim=900, force=True)
C.OUT["ops_metrics_econ"] = C.ops_metrics(m)
C._dump()
print("ops_metrics_econ stored")
