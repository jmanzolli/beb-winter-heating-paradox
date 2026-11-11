#!/bin/bash
# Runs requested by the review of 2026-11-09 (TR-C manuscript main_2).
# Self-contained: run from the bundle directory (model code + inputs copied in),
# so nothing in ~/v8run is overwritten.
#
#   M1  heater installed capital 15 / 17.5 / 20 / 25 / 30 kCAD at lambda = 0,
#       MIP-started from the cheapest archived design at each price
#   M2-M4, M3
#       reliability protocol v10 (band-conditional traction residuals with a
#       day-level factor, sampled day temperature, data-implied heat CV,
#       reserve-compliant / trips-completed / comfort outcomes) for
#         D0, D4, the 25 and 100 kWh reserve designs, the design-day design
#       at levels trac, data, cv0.20; D0 and D4 also at trac_fixT
#   M8  design-day design evaluated on the full scenario set (and D0 by the
#       same fixed-design procedure)
#   M7  division: route-locked case B and full coordination D, both
#       MIP-started from the shared-pool case C
#
# Usage:  nohup ./run_review_v10.sh > run_review_v10.log 2>&1 &
cd "$(dirname "$0")"
PY=${PY:-$HOME/grbenv/bin/python}
export GRB_LICENSE_FILE=${GRB_LICENSE_FILE:-$HOME/gurobi.lic}
IN=route52_inputs_v9.json
GIN=garage_inputs_v9.json
RES=campaign_v9rev_results.json
N=${REL_N:-1000}
mkdir -p lanes logs logs_div
run_soft () { local n="$1"; shift; echo "=== $n === $(date)"
  if "$@"; then echo "--- $n OK $(date)"; else echo "!!! $n FAILED (exit $?) $(date)"; fi; }
rel () {  # rel RESULTS DESIGN LEVELS OUT
  env ROUTE_INPUTS=$IN REL_RESULTS=$1 REL_DESIGN=$2 REL_LEVELS=$3 REL_OUT=$4 \
      REL_INPUTS=rel_inputs_v10.json REL_WINTERS=eccc_winter_bands_v9.json \
      REL_LAM=0 REL_THREADS=2 "$PY" reliability_v10.py $N; }
camp () {  # camp THREADS OUT script args...
  local th=$1 out=$2; shift 2
  env ROUTE_INPUTS=$IN CAMP_OUT=$out CAMP_LOGDIR=logs CAMP_THREADS=$th \
      CAMP_MEM_GB=12 CAMP_NODEFILE_GB=8 REVIEW_SRC=$RES "$PY" "$@"; }

echo "run_review_v10 started $(date) on $(hostname), N=$N per band"
"$PY" -c "import gurobipy; print('gurobi', gurobipy.gurobi.version())" || exit 1
P=()

# ---- M2-M4 / M3 / M8 reliability (17 processes x 2 threads)
declare -A SRC=( [econ_lam0]=$RES [eps_0.00]=$RES
                 [relmatch_eps0_r25]=relmatch_v9.json [relmatch_eps0_r100]=relmatch_v9.json
                 [det_designday]=rev_designday_v9.json )
for d in econ_lam0 eps_0.00 relmatch_eps0_r25 relmatch_eps0_r100 det_designday; do
  for lv in trac data cv0.20; do
    ( run_soft "rel $d $lv" rel ${SRC[$d]} $d $lv rel_v10_${d}_${lv}.json ) \
      > lanes/rel_${d}_${lv}.log 2>&1 & P+=($!)
  done
done
for d in econ_lam0 eps_0.00; do
  ( run_soft "rel $d trac_fixT" rel ${SRC[$d]} $d trac_fixT rel_v10_${d}_trac_fixT.json ) \
    > lanes/rel_${d}_trac_fixT.log 2>&1 & P+=($!)
done

# ---- M1 heater capital (5 processes x 4 threads)
for fc in 15000 17500 20000 25000 30000; do
  ( export REVIEW_CAPEX=$fc
    run_soft "capex $fc" camp 4 rev10_capex_$fc.json review_runs_v10.py capex ) \
    > lanes/capex_$fc.log 2>&1 & P+=($!)
done

# ---- M8 fixed-design evaluations (2 processes x 4 threads)
( run_soft "design-day eval" camp 4 rev10_ddeval.json review_runs_v10.py ddeval ) \
  > lanes/ddeval.log 2>&1 & P+=($!)
( run_soft "D0 eval" camp 4 rev10_d0eval.json review_runs_v10.py d0eval ) \
  > lanes/d0eval.log 2>&1 & P+=($!)

# ---- M7 division, B and D warm-started from C (2 processes x 8 threads, 6 h)
for c in B D; do
  ( run_soft "division $c" env ROUTE_INPUTS=$GIN DIV_LOGDIR=logs_div DIV_THREADS=8 \
      DIV_MEM_GB=24 DIV_NODEFILE_GB=16 DIV_TLIM=21600 DIV_OUT=div10_$c.json \
      DIV_START_FROM=campaign_division_v9rev.json:C_shared_infra_frozen_z \
      DIV_START_ROUTELOCK=1 "$PY" campaign_division_v5.py $c ) \
    > lanes/div_$c.log 2>&1 & P+=($!)
done

wait "${P[@]}"
touch REVIEW_V10_DONE
echo "=== review v10 runs done $(date)"
grep -h '!!!' lanes/*.log || echo "all stages OK"
