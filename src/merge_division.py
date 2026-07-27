"""
Merge per-case division result shards into one file.

When the cases are run as concurrent processes (each with its own DIV_OUT),
this collects the shards into campaign_division_v5.json so everything
downstream sees a single file. If a case appears in more than one shard, the
one with the tighter absolute gap is kept and the collision is reported.

Usage: python3 merge_division.py [out.json] [shard.json ...]
       python3 merge_division.py                 # defaults: div_*.json
"""

import glob
import json
import sys

args = [a for a in sys.argv[1:]]
out_file = args[0] if args else "campaign_division_v5.json"
shards = args[1:] or sorted(glob.glob("div_*.json"))

if not shards:
    print("no shards found (expected div_*.json)")
    raise SystemExit(1)

merged = {"cases": {}, "meta": {"shards": shards}}
for fn in shards:
    d = json.load(open(fn))
    for name, rec in d.get("cases", {}).items():
        prev = merged["cases"].get(name)
        if prev is None:
            merged["cases"][name] = rec
            continue
        pg, ng = prev.get("abs_gap", 9e18), rec.get("abs_gap", 9e18)
        keep = rec if ng < pg else prev
        print(f"collision on {name}: gaps {pg} vs {ng}, keeping {min(pg, ng)}")
        merged["cases"][name] = keep
    if "meta" in d:
        merged["meta"].setdefault("per_shard_meta", {})[fn] = d["meta"]

json.dump(merged, open(out_file, "w"), indent=1)
print(f"merged {len(shards)} shards -> {out_file}: "
      f"{sorted(merged['cases'])}")
