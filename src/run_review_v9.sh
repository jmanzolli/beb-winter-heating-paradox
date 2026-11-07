#!/bin/bash
# Runs requested by the 2026-11-06 internal review (v9 instance, same model).
#   R1  reliability re-run with a slack-only recourse objective (tight tolerance)
#       and the shortfall split by constraint: D0 and D4 at heat CV 0/0.2/0.4,
#       the four raised-reserve FFH-free designs at CV 0; band re-check of the
#       mean-temperature design, D0 and D4 with the same objective
#   R2  FFH capital-cost bisection (7.5 / 10 / 12.5 kCAD per heater)
#   R3  fragmented division re-solved per route without the "none" site and
#       with depot load profiles, then re-billed on one shared depot meter
#   R4  D3 lexicographic phase 2 re-run with a MIP start from lam_5000
#   R7  design-day deterministic benchmark (+ band re-check)
#   m6  fractional scenario weights (econ baseline and FFH-free endpoint)
# Usage:  nohup ./run_review_v9.sh > run_review_v9.log 2>&1 &
cd "$(dirname "$0")"
PY=${PY:-$HOME/grbenv/bin/python}
export GRB_LICENSE_FILE=${GRB_LICENSE_FILE:-$HOME/gurobi.lic}
IN=route52_inputs_v9.json
GIN=garage_inputs_v9.json
RES=campaign_v9_results.json
mkdir -p lanes_rev logs_rev logs_rev_div
run_soft () { local n="$1"; shift; echo "=== $n === $(date)"
  if "$@"; then echo "--- $n OK $(date)"; else echo "!!! $n FAILED (exit $?) $(date)"; fi; }
rel () {  # rel RESULTS DESIGN CVS OUT
  env ROUTE_INPUTS=$IN REL_RESULTS=$1 REL_DESIGN=$2 REL_LAM=0 REL_HEAT_CVS=$3 \
      REL_POOL=v7_residual_pool.json REL_OUT=$4 REL_SLACK_ONLY=1 "$PY" reliability_v5.py 1000; }
camp () {  # camp THREADS OUT INPUTS script args...
  local th=$1 out=$2 inp=$3; shift 3
  env ROUTE_INPUTS=$inp CAMP_OUT=$out CAMP_LOGDIR=logs_rev CAMP_THREADS=$th \
      CAMP_MEM_GB=12 CAMP_NODEFILE_GB=8 "$PY" "$@"; }
echo "run_review_v9 started $(date) on $(hostname)"
P=()
# ---- R1 reliability (10 processes)
for cv in 0.0 0.20 0.40; do t=$(echo $cv | tr -d .); 
  ( run_soft "rel D0 cv$cv" rel $RES econ_lam0 $cv relrev_v9_econ_cv$t.json ) > lanes_rev/rel_d0_$t.log 2>&1 & P+=($!)
  ( run_soft "rel D4 cv$cv" rel $RES eps_0.00 $cv relrev_v9_zero_cv$t.json ) > lanes_rev/rel_d4_$t.log 2>&1 & P+=($!)
done
for r in 25 50 75 100; do
  ( run_soft "rel relmatch r$r" rel relmatch_v9.json relmatch_eps0_r$r 0.0 relrev_v9_relmatch_r$r.json ) > lanes_rev/rel_rm_$r.log 2>&1 & P+=($!)
done
( run_soft "band re-check" env ROUTE_INPUTS=$IN DETBAND_RES=$RES DETBAND_OUT=detbandrev_v9.json \
    DETBAND_SLACK_ONLY=1 DETBAND_LABELS=det_meanT,econ_lam0,eps_0.00 "$PY" detband_check.py ) > lanes_rev/detband.log 2>&1 & P+=($!)
# ---- R2 heater capital cost (3 processes)
for fc in 7500 10000 12500; do
  ( run_soft "capex $fc" env REVIEW_CAPEX=$fc ROUTE_INPUTS=$IN CAMP_OUT=rev_capex_$fc.json CAMP_LOGDIR=logs_rev CAMP_THREADS=4 CAMP_MEM_GB=12 CAMP_NODEFILE_GB=8 "$PY" review_runs_v9.py capex ) \
    > lanes_rev/capex_$fc.log 2>&1 & P+=($!)
done
# REVIEW_CAPEX per process
# ---- R4 D3 phase 2
( run_soft "D3 phase 2" camp 6 rev_d3_v9.json $IN review_runs_v9.py d3 ) > lanes_rev/d3.log 2>&1 & P+=($!)
# ---- R7 design-day benchmark, then its band re-check
( run_soft "design day" camp 4 rev_designday_v9.json $IN review_runs_v9.py designday
  run_soft "design day band re-check" env ROUTE_INPUTS=$IN DETBAND_RES=rev_designday_v9.json \
      DETBAND_OUT=detband_designday_v9.json DETBAND_SLACK_ONLY=1 DETBAND_LABELS=det_designday "$PY" detband_check.py
) > lanes_rev/designday.log 2>&1 & P+=($!)
# ---- m6 fractional weights
( run_soft "fractional weights" camp 6 addon_fracw_v9.json route52_inputs_v9_fracw.json sev_sweep_v8.py ) \
  > lanes_rev/fracw.log 2>&1 & P+=($!)
# ---- R3 fragmented division, 14 routes in parallel
ROUTES=$("$PY" -c 'import json,re; b=json.load(open("garage_inputs_v9.json"))["branches"]; print(" ".join(sorted({re.match(r"r(\d+)",k).group(1) for k in b})))')
echo "routes: $ROUTES"
DP=()
for r in $ROUTES; do
  ( run_soft "fragmented route $r" env ROUTE_INPUTS=$GIN DIV_LOGDIR=logs_rev_div DIV_MEM_GB=8 \
      DIV_NODEFILE_GB=8 DIV_OUT=divrev_A_route_$r.json DIV_THREADS=2 DIV_ROUTES=$r "$PY" campaign_division_v5.py A
  ) > lanes_rev/div_route_$r.log 2>&1 & DP+=($!)
done
wait "${DP[@]}"
cp -f campaign_division_v9.json campaign_division_v9_rev.json
run_soft "merge fragmented" env ROUTE_INPUTS=$GIN "$PY" merge_fragmented_v9.py campaign_division_v9_rev.json divrev_A_route_*.json \
  > lanes_rev/div_merge.log 2>&1
wait "${P[@]}"
touch REVIEW_V9_DONE
echo "=== review runs done $(date)"
grep -h '!!!' lanes_rev/*.log || echo "all stages OK"
