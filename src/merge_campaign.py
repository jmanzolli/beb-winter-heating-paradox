"""
Merge Route 52 campaign shards into one result file.

When sensitivity subsets run as concurrent processes (each with its own
CAMP_OUT), this collects them back. If a label appears in more than one
shard, the record with the tighter absolute gap wins and the collision is
reported -- the same rule the campaign's own refinement pass uses, so a
re-solve never loses to a looser earlier attempt.

Usage: python3 merge_campaign.py [out.json] [shard.json ...]
       python3 merge_campaign.py                 # defaults: sh_*.json
"""

import glob
import json
import sys

args = sys.argv[1:]
out_file = args[0] if args else "campaign_v5_results.json"
shards = args[1:] or sorted(glob.glob("sh_*.json"))
if not shards:
    print("no shards found (expected sh_*.json)")
    raise SystemExit(1)

best, order, meta = {}, [], {}
for fn in shards:
    d = json.load(open(fn))
    meta.update(d.get("meta", {}))
    for k in ("ops_metrics_policy", "frontier_labels", "breakpoint_prices",
              "det_feasible_full", "n_minus_1_feasible", "derived"):
        if k in d:
            meta.setdefault("_carried", {})[k] = d[k]
    for r in d.get("runs", []):
        lb = r["label"]
        if lb not in best:
            best[lb], _ = r, order.append(lb)
            continue
        pg = best[lb].get("abs_gap", 9e18)
        ng = r.get("abs_gap", 9e18)
        if ng < pg:
            print(f"collision on {lb}: gap {pg} -> {ng} (keeping tighter)")
            best[lb] = r
        elif ng > pg:
            print(f"collision on {lb}: gap {ng} discarded (kept {pg})")

merged = {"runs": [best[lb] for lb in order], "meta": meta}
for k, v in meta.pop("_carried", {}).items():
    merged[k] = v
json.dump(merged, open(out_file, "w"), indent=1)
hosts = sorted({r.get("host", "?") for r in merged["runs"]})
print(f"merged {len(shards)} shards -> {out_file}: "
      f"{len(merged['runs'])} runs from hosts {hosts}")
