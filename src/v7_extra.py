"""Severe-band traction factor and FFH-rating sensitivities (v7).
Run per variant: ROUTE_INPUTS=<variant.json> CAMP_OUT=<variant_results.json>
"""
import campaign_v5 as C

C.solve("econ_lam0", lam=0.0)
C.solve("eps_0.00", eps=0.0, lam=0.0, lexicographic=True, tlim=7200)
print("extra runs complete")
