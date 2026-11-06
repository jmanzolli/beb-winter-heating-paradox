#!/bin/bash
# v9 re-run (2026-11-05). Same model and thermal inputs as v8, with:
#   base changes
#   - cost parameters of the companion study (Liu et al., Applied Energy, in
#     press, Table C.1): demand charge 18.06 CAD/kW-month (Toronto Hydro GS
#     50-999 kW, 2026; division depot 16.08, GS 1,000-4,999 kW), extended-
#     battery traction penalty +3.7%, charger cost point 160 kCAD at 120 kW
#   - energy price: 0.12 CAD/kWh level (companion) + hourly HOEP deviation
#     (winter Nov 2024-Mar 2025, off-season Apr-Oct 2024), replacing the
#     residential TOU schedule
#   - scenario weights: 24 winters (2002-03 to 2025-26) of ECCC Toronto City
#     daily mean temperature: 83/38/21/7/2 winter days, off-season 16.8 C
#   - division: stop at 6 h or 0.5% relative gap
#   add-ons (economic baseline + FFH-free endpoint per variant)
#   - heat-pump COP, useful fraction 0.55/0.60, cabin heat -6%/+3.5%, burner
#     fuel 70%/115%, minimum depot plug session 30/60 min, battery wear,
#     daily-minimum (cold) weighting
#
# The WLS Compute Server licence accepts concurrent sessions, so the work runs
# in parallel lanes (threads/memory sized for the 80-core host). Each solve
# stage resumes: a label already in its output file is skipped.
#
# Usage:  nohup ./run_all_v9.sh > run_all_v9.log 2>&1 &
cd "$(dirname "$0")"

PY=${PY:-$HOME/grbenv/bin/python}
[ -x "$PY" ] || PY=python3
export GRB_LICENSE_FILE=${GRB_LICENSE_FILE:-$HOME/gurobi.lic}

IN=route52_inputs_v9.json
GIN=garage_inputs_v9.json
RES=campaign_v9_results.json
DIV=campaign_division_v9.json
mkdir -p logs_v9 logs_div_v9 ieee_figs lanes_v9

echo "host $(hostname) | $(nproc) cores | py $PY | started $(date)"

"$PY" - <<'EOF' || exit 1
import gurobipy as gp
m = gp.Model(); m.addVar(); m.update()
print("licence OK:", gp.gurobi.version())
EOF

ROUTE_INPUTS=$IN "$PY" - <<'EOF' || exit 1
import route52_prototype as R
print("v9 check | demand", R.DEMAND_CHARGE_MONTH, "| mass", R.MASS_PEN_EXT,
      "| chargers", R.CHARGER_COST_POINTS[2], "| days",
      {w: R.SCEN[w][1] for w in R.SCEN}, "| price 07h winter", R.tou(9, "mild"))
assert R.DEMAND_CHARGE_MONTH == 18.06 and R.MASS_PEN_EXT == 0.037
assert R.CHARGER_COST_POINTS[2] == (120, 160000)
assert R.SCEN["severe"][1] == 2 and R.ENERGY_PRICE_HOURLY
EOF

echo "=== 0. model self-checks === $(date)"
ROUTE_INPUTS=$IN "$PY" test_v5.py || exit 1

# run_soft NAME CMD... : log the stage, never abort the lane
run_soft () {
  local name="$1"; shift
  echo "=== $name === $(date)"
  if "$@"; then echo "--- $name OK $(date)"
  else echo "!!! $name FAILED (exit $?) $(date)"; fi
}
camp () {  # camp THREADS MEMGB LOGDIR OUT INPUTS script args...
  local th=$1 mem=$2 ld=$3 out=$4 inp=$5; shift 5
  env ROUTE_INPUTS=$inp CAMP_OUT=$out CAMP_LOGDIR=$ld CAMP_THREADS=$th \
      CAMP_MEM_GB=$mem CAMP_NODEFILE_GB=8 "$PY" "$@"
}
rel () {  # rel RESULTS DESIGN CVS OUT
  env ROUTE_INPUTS=$IN REL_RESULTS=$1 REL_DESIGN=$2 REL_LAM=0 REL_HEAT_CVS=$3 \
      REL_POOL=v7_residual_pool.json REL_OUT=$4 "$PY" reliability_v5.py 1000
}
for d in core bench sensA sensB misc add1; do mkdir -p logs_v9_$d; done

# ---------------- lane 1: campaign core (baselines, frontier, prices) ------
( run_soft "core" camp 14 32 logs_v9_core sh_core_v9.json $IN campaign_v9_part.py core
) > lanes_v9/core.log 2>&1 &
P_CORE=$!
# ---------------- lane 2: benchmarks ---------------------------------------
( run_soft "bench" camp 8 16 logs_v9_bench sh_bench_v9.json $IN campaign_v9_part.py bench
) > lanes_v9/bench.log 2>&1 &
P_BENCH=$!
# ---------------- lanes 3-4: sensitivities ---------------------------------
( run_soft "sensA" camp 8 16 logs_v9_sensA sh_sensA_v9.json $IN campaign_v9_part.py sensA
  run_soft "batt_50" camp 8 16 logs_v9_sensA sh_sensA_v9.json $IN batt50_run.py
) > lanes_v9/sensA.log 2>&1 &
P_SA=$!
( run_soft "sensB" camp 8 16 logs_v9_sensB sh_sensB_v9.json $IN campaign_v9_part.py sensB
) > lanes_v9/sensB.log 2>&1 &
P_SB=$!
# ---------------- lane 5: independent follow-ups, then add-ons -------------
( run_soft "relmatch designs" camp 8 16 logs_v9_misc relmatch_v9.json $IN relmatch_run.py
  for G in 25 50 75 100; do
    run_soft "relmatch reliability r$G" rel relmatch_v9.json relmatch_eps0_r$G 0.0 rel_v9_relmatch_eps0_r$G.json
  done
  run_soft "calibration sweep" env ROUTE_INPUTS=$IN CAMP_OUT=calib_chargers_results_v9.json \
      CAMP_LOGDIR=logs_v9_misc CALIB_OUT=calib_chargers_v9.json CAMP_THREADS=8 "$PY" calib_chargers.py
  run_soft "severe factor 1.15" camp 8 16 logs_v9_misc sev115_v9.json route52_inputs_v9_sev115.json sev_sweep_v8.py
  run_soft "severe factor 1.30" camp 8 16 logs_v9_misc sev130_v9.json route52_inputs_v9_sev130.json sev_sweep_v8.py
  for t in hp plug30 plug60 coldw wear; do
    run_soft "add-on $t" camp 8 16 logs_v9_misc addon_${t}_v9.json route52_inputs_v9_$t.json sev_sweep_v8.py
  done
) > lanes_v9/misc.log 2>&1 &
P_MISC=$!
# ---------------- lane 6: add-ons (companion ranges) -----------------------
( for t in phi055 phi060 heat094 heat1035 fuel070 fuel115; do
    run_soft "add-on $t" camp 8 16 logs_v9_add1 addon_${t}_v9.json route52_inputs_v9_$t.json sev_sweep_v8.py
  done
) > lanes_v9/add1.log 2>&1 &
P_ADD=$!
# ---------------- lane 7: division (C, D warm-started from C, A, stability)
DIVENV="ROUTE_INPUTS=$GIN DIV_OUT=$DIV DIV_LOGDIR=logs_div_v9 DIV_THREADS=18 DIV_MEM_GB=50 DIV_NODEFILE_GB=16 DIV_TLIM=21600 DIV_MIPGAP=0.005"
( run_soft "division C" env $DIVENV "$PY" campaign_division_v5.py C
  run_soft "division D" env $DIVENV DIV_START_FROM=$DIV:C_shared_infra_frozen_z "$PY" campaign_division_v5.py D
  run_soft "division A + stability" env $DIVENV "$PY" campaign_division_v5.py A stability
) > lanes_v9/division.log 2>&1 &
P_DIV=$!

echo "lanes started: core $P_CORE bench $P_BENCH sensA $P_SA sensB $P_SB misc $P_MISC add1 $P_ADD division $P_DIV"

# ---------------- merge the campaign shards, then post-processing ----------
wait $P_CORE $P_BENCH $P_SA $P_SB
echo "=== campaign shards done === $(date)"
"$PY" merge_campaign.py $RES sh_bench_v9.json sh_sensA_v9.json sh_sensB_v9.json sh_core_v9.json
for d in bench sensA sensB core; do cp -f logs_v9_$d/* logs_v9/ 2>/dev/null; done

(
run_soft "econ_lam0 lexicographic re-solve" camp 14 32 logs_v9 $RES $IN econ_lex_run.py
run_soft "econ_lam0 ops record" camp 14 32 logs_v9 $RES $IN v7_econ_ops.py
run_soft "mean-temperature per-band check" env ROUTE_INPUTS=$IN DETBAND_RES=$RES DETBAND_OUT=detband_v9.json "$PY" detband_check.py
run_soft "reliability econ cv 0/0.20/0.40" rel $RES econ_lam0 0.0,0.20,0.40 rel_v9_econ_full.json &
run_soft "reliability FFH-free cv 0" rel $RES eps_0.00 0.0 rel_v9_zero_cv00.json &
run_soft "soft heat balance and VSS" env ROUTE_INPUTS=$IN CAMP_OUT=evpi_vss_results_v9.json \
    CAMP_LOGDIR=logs_v9 EVPI_SRC=$RES EVPI_OUT=evpi_vss_v9.json CAMP_THREADS=8 "$PY" evpi_vss_run.py &
for f in ieee_figs/fig6_*; do [ -e "$f" ] && cp -n "$f" "${f%.*}_v8.${f##*.}"; done 2>/dev/null
run_soft "severe-day figure" env ROUTE_INPUTS=$IN FIG6_RES=$RES "$PY" ieee_fig6.py &
wait
run_soft "provenance" env PROV_RES=$RES PROV_OUT=provenance_v9.json PROV_LOGDIR=logs_v9 "$PY" make_provenance_v5.py
run_soft "integrity checks" env ROUTE_INPUTS=$IN CHECK_RES=$RES CHECK_PROV=provenance_v9.json "$PY" check_results_v5.py
) > lanes_v9/post.log 2>&1
echo "=== Route 52 post-processing done === $(date)"
touch ROUTE52_V9_DONE

wait $P_MISC $P_ADD
echo "=== follow-ups and add-ons done === $(date)"
touch ADDONS_V9_DONE
wait $P_DIV
echo "=== division done === $(date)"
touch DIVISION_V9_DONE
echo "=== v9 complete === $(date)"
grep -h '!!!' lanes_v9/*.log || echo "all stages OK"
