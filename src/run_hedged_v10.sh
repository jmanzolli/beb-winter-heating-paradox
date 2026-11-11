#!/bin/bash
# Reliability protocol v10 with a hedged day-ahead assignment (2026-11-10).
#
# The first v10 runs fixed the block-to-bus-class assignment from the
# cost-minimising planning solve. That solve is indifferent between many
# assignments, so in a mixed fleet the heater and extended-range buses landed
# on arbitrary blocks. This re-run gives the two affected designs
#   det_designday        3 heater + 13 standard + 2 extended-range buses
#   relmatch_eps0_r100   16 standard + 2 extended-range buses
# the assignment that tolerates the largest uniform rise in traction energy on
# a cold day of each band (reliability_v10.py, hedged_assignment), at levels
# trac, data and cv0.20. Draws, seed and outcome definitions are unchanged, so
# the results are comparable with rel_v10_*.json draw by draw. D0 and the
# 25 kWh reserve design have one bus class; D4 was checked and is unaffected.
#
# Stages: 1  one assignment per design (assign_v10h_<design>.json)
#         2  each design x level split into REL_CHUNKS processes of 2 threads
#         3  merge into rel_v10h_<design>_<level>.json
#
# Usage:  nohup ./run_hedged_v10.sh > run_hedged_v10.log 2>&1 &
cd "$(dirname "$0")"
PY=${PY:-$HOME/grbenv/bin/python}
export GRB_LICENSE_FILE=${GRB_LICENSE_FILE:-$HOME/gurobi.lic}
N=${REL_N:-1000}
NC=${REL_CHUNKS:-6}
DESIGNS=${REL_DESIGNS:-"det_designday relmatch_eps0_r100"}
LEVELS=${REL_LEVELS_H:-"trac data cv0.20"}
declare -A SRC=( [det_designday]=rev_designday_v9.json
                 [relmatch_eps0_r100]=relmatch_v9.json
                 [relmatch_eps0_r25]=relmatch_v9.json
                 [econ_lam0]=campaign_v9rev_results.json
                 [eps_0.00]=campaign_v9rev_results.json )
mkdir -p lanes_h shards_h
rel () {  # rel DESIGN THREADS [VAR=value ...] -- args...
  local d=$1 th=$2; shift 2
  local extra=()
  while [ "$1" != "--" ]; do extra+=("$1"); shift; done; shift
  env ROUTE_INPUTS=route52_inputs_v9.json REL_RESULTS=${SRC[$d]} REL_DESIGN=$d \
      REL_INPUTS=rel_inputs_v10.json REL_WINTERS=eccc_winter_bands_v9.json \
      REL_LAM=0 REL_THREADS=$th "${extra[@]}" "$PY" -u reliability_v10.py "$@"; }

echo "run_hedged_v10 started $(date) on $(hostname), N=$N per band, $NC chunks"
"$PY" -c "import gurobipy; print('gurobi', gurobipy.gurobi.version())" || exit 1
rm -f HEDGED_V10_DONE

# ---- 1. assignments
P=()
for d in $DESIGNS; do
  ( rel $d 16 -- assign assign_v10h_$d.json ) > lanes_h/assign_$d.log 2>&1 & P+=($!)
done
wait "${P[@]}"
for d in $DESIGNS; do
  if [ -s assign_v10h_$d.json ]; then echo "--- assignment $d OK $(date)"
  else echo "!!! assignment $d FAILED $(date)"; fi
done

# ---- 2. chunks
P=()
for d in $DESIGNS; do
  [ -s assign_v10h_$d.json ] || continue
  for lv in $LEVELS; do
    for ((c = 0; c < NC; c++)); do
      ( rel $d 2 REL_ASSIGN=assign_v10h_$d.json REL_LEVELS=$lv REL_CHUNK=$c/$NC \
            REL_OUT=shards_h/rel_v10h_${d}_${lv}_c$c.json -- $N ) \
        > lanes_h/rel_${d}_${lv}_c$c.log 2>&1 & P+=($!)
    done
  done
done
wait "${P[@]}"
echo "=== chunks done $(date)"

# ---- 3. merge
for d in $DESIGNS; do
  [ -s assign_v10h_$d.json ] || continue
  for lv in $LEVELS; do
    S=()
    for ((c = 0; c < NC; c++)); do S+=(shards_h/rel_v10h_${d}_${lv}_c$c.json); done
    if rel $d 2 REL_LEVELS=$lv -- merge rel_v10h_${d}_${lv}.json "${S[@]}" \
         > lanes_h/merge_${d}_${lv}.log 2>&1
    then echo "--- merge $d $lv OK"; else echo "!!! merge $d $lv FAILED"; fi
  done
done
touch HEDGED_V10_DONE
echo "=== hedged v10 runs done $(date)"
