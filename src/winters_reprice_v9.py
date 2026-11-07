"""Re-price the economic baseline (D0) and the FFH-free design (D4) against
each of the 24 historical winters (review item R7).

The designs and their per-band daily operation are those of the planning
solution (campaign_v9_results.json, scen_ops). Capital, demand charges and
the off-season day do not depend on the winter's band mix, so only the
weighted daily operating cost and diesel change: for winter y,
  cost_y = F1 + sum_w (days_{w,y} - h_w) * opex_w,
  co2_y  = sum_w days_{w,y} * diesel_w * 2.68 kg/L.
Writes winters_reprice_v9.json and prints the range across winters.
"""
import json

import route52_prototype as R

runs = {r["label"]: r for r in json.load(open("campaign_v9_results.json"))["runs"]}
W = json.load(open("data_v9/eccc_winter_bands_v9.json"))["winters"]
B = ["mild", "cold", "verycold", "extreme", "severe"]
out = {"note": __doc__.strip(), "winters": {}}
for lb in ("econ_lam0", "eps_0.00"):
    r = runs[lb]
    so = r["scen_ops"]
    opex = {w: so[w]["electricity_cost"] + R.DIESEL_PRICE * so[w]["diesel_L"] for w in B}
    for y, cnt in W.items():
        c = r["F1"] + sum((cnt[w] - R.SCEN[w][1]) * opex[w] for w in B)
        e = sum(cnt[w] * so[w]["diesel_L"] for w in B) * 2.68 / 1e3
        out["winters"].setdefault(y, {})[lb] = {"cost_kCAD": round(c / 1e3, 2),
                                                "co2_t": round(e, 2)}
prem = {y: v["eps_0.00"]["cost_kCAD"] - v["econ_lam0"]["cost_kCAD"]
        for y, v in out["winters"].items()}
for y in out["winters"]:
    out["winters"][y]["premium_kCAD"] = round(prem[y], 2)
co2 = {y: v["econ_lam0"]["co2_t"] for y, v in out["winters"].items()}
c0 = {y: v["econ_lam0"]["cost_kCAD"] for y, v in out["winters"].items()}
out["summary"] = {
    "premium_kCAD_min_max": [round(min(prem.values()), 1), round(max(prem.values()), 1)],
    "premium_min_winter": min(prem, key=prem.get), "premium_max_winter": max(prem, key=prem.get),
    "baseline_co2_t_min_max": [round(min(co2.values()), 1), round(max(co2.values()), 1)],
    "baseline_cost_kCAD_min_max": [round(min(c0.values()), 1), round(max(c0.values()), 1)],
}
json.dump(out, open("winters_reprice_v9.json", "w"), indent=1)
print(json.dumps(out["summary"], indent=1))
for y in sorted(W):
    print(y, W[y]["extreme"] + W[y]["severe"], out["winters"][y]["econ_lam0"]["co2_t"], prem[y])
