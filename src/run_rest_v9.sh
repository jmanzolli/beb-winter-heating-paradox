#!/bin/bash
# v9 acceleration (2026-11-05, ~14:00 WET). Replaces the remaining serial
# parts of run_all_v9.sh, which was stopped after 8 h with the core lane on
# its 5th frontier point and the misc lane on reliability r75:
#   - frontier points, carbon prices, breakpoints and refinements run as
#     one-label shards in parallel (shard_solve_v9.py), then core_finish_v9.py
#     writes frontier_labels/breakpoint_prices and runs the monotonicity check
#   - remaining follow-ups and add-ons run as three parallel chains
#   - division A runs now in its own file; stability runs after D finishes
#   - the economic-baseline reliability splits by heat CV into three processes
# Same solves, labels, limits and inputs as run_all_v9.sh; only thread counts
# per process are smaller. Still-running processes left alone: division D,
# reliability r75, the add1 lane (fuel115).
#
# Usage:  nohup ./run_rest_v9.sh > run_rest_v9.log 2>&1 &
cd "$(dirname "$0")"

PY=${PY:-$HOME/grbenv/bin/python}
[ -x "$PY" ] || PY=python3
export GRB_LICENSE_FILE=${GRB_LICENSE_FILE:-$HOME/gurobi.lic}

IN=route52_inputs_v9.json
GIN=garage_inputs_v9.json
RES=campaign_v9_results.json
DIV=campaign_division_v9.json
mkdir -p lanes_v9 logs_v9 logs_v9_core logs_v9_misc logs_div_v9

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
shard () {  # shard LABEL THREADS
  local lb=$1 th=$2
  local f="sh_x_$(echo "$lb" | tr ':.' '__')_v9.json"
  run_soft "shard $lb" env CORE_SRC=sh_core_v9.json ROUTE_INPUTS=$IN CAMP_OUT=$f \
      CAMP_LOGDIR=logs_v9_core CAMP_THREADS=$th CAMP_MEM_GB=12 CAMP_NODEFILE_GB=8 \
      "$PY" shard_solve_v9.py "$lb"
}
alive () { pgrep -u "$USER" -f "$1" > /dev/null; }

echo "run_rest_v9 started $(date) on $(hostname)"

# ---------------- follow-ups and add-ons: three chains + reliability r100 --
( run_soft "relmatch reliability r100" rel relmatch_v9.json relmatch_eps0_r100 0.0 rel_v9_relmatch_eps0_r100.json
) > lanes_v9/rel100.log 2>&1 &
P_R100=$!
( for t in sev115 hp plug30; do
    f=route52_inputs_v9_$t.json; o=addon_${t}_v9.json
    [ $t = sev115 ] && o=sev115_v9.json
    run_soft "add-on $t" camp 4 12 logs_v9_misc $o $f sev_sweep_v8.py
  done
) > lanes_v9/chainA.log 2>&1 &
P_CA=$!
( for t in sev130 plug60 coldw; do
    f=route52_inputs_v9_$t.json; o=addon_${t}_v9.json
    [ $t = sev130 ] && o=sev130_v9.json
    run_soft "add-on $t" camp 4 12 logs_v9_misc $o $f sev_sweep_v8.py
  done
) > lanes_v9/chainB.log 2>&1 &
P_CB=$!
( run_soft "calibration sweep" env ROUTE_INPUTS=$IN CAMP_OUT=calib_chargers_results_v9.json \
      CAMP_LOGDIR=logs_v9_misc CALIB_OUT=calib_chargers_v9.json CAMP_THREADS=4 "$PY" calib_chargers.py
  run_soft "add-on wear" camp 4 12 logs_v9_misc addon_wear_v9.json route52_inputs_v9_wear.json sev_sweep_v8.py
) > lanes_v9/chainC.log 2>&1 &
P_CC=$!

# ---------------- division A in its own file (D still running) -------------
DIVENV="ROUTE_INPUTS=$GIN DIV_LOGDIR=logs_div_v9 DIV_MEM_GB=40 DIV_NODEFILE_GB=16 DIV_TLIM=21600 DIV_MIPGAP=0.005"
( run_soft "division A" env $DIVENV DIV_OUT=campaign_division_v9_A.json DIV_THREADS=6 "$PY" campaign_division_v5.py A
) > lanes_v9/divisionA.log 2>&1 &
P_DA=$!

# ---------------- Route 52 core: shards ------------------------------------
(
pids=()
for lb in eps_0.20 eps_0.10 eps_0.00 lam_200 lam_500 lam_1000 lam_2000 lam_3500 lam_5000 lam_10000; do
  shard $lb 4 & pids+=($!)
done
wait "${pids[@]}"
"$PY" merge_campaign.py sh_core_v9.json sh_core_v9.json sh_x_eps_*_v9.json sh_x_lam_*_v9.json

pids=()
for v in $(env ROUTE_INPUTS=$IN CAMP_OUT=sh_core_v9.json CAMP_LOGDIR=logs_v9_core "$PY" core_finish_v9.py bps | grep -E '^[0-9]+$'); do
  shard bp_lam_$v 6 & pids+=($!)
done
for lb in $(env ROUTE_INPUTS=$IN CAMP_OUT=sh_core_v9.json CAMP_LOGDIR=logs_v9_core "$PY" core_finish_v9.py loose | grep -E '^eps_'); do
  shard refine:$lb 6 & pids+=($!)
done
wait "${pids[@]}"
ls sh_x_bp_lam_*_v9.json sh_x_refine_*_v9.json > /dev/null 2>&1 && \
  "$PY" merge_campaign.py sh_core_v9.json sh_core_v9.json $(ls sh_x_bp_lam_*_v9.json sh_x_refine_*_v9.json 2>/dev/null)
run_soft "core finish" camp 14 32 logs_v9_core sh_core_v9.json $IN core_finish_v9.py final
) > lanes_v9/core2.log 2>&1
echo "=== core done === $(date)"

"$PY" merge_campaign.py $RES sh_bench_v9.json sh_sensA_v9.json sh_sensB_v9.json sh_core_v9.json
for d in bench sensA sensB core; do cp -f logs_v9_$d/* logs_v9/ 2>/dev/null; done

# ---------------- Route 52 post-processing ---------------------------------
(
run_soft "econ_lam0 lexicographic re-solve" camp 14 32 logs_v9 $RES $IN econ_lex_run.py
run_soft "econ_lam0 ops record" camp 14 32 logs_v9 $RES $IN v7_econ_ops.py
run_soft "mean-temperature per-band check" env ROUTE_INPUTS=$IN DETBAND_RES=$RES DETBAND_OUT=detband_v9.json "$PY" detband_check.py &
run_soft "reliability econ cv 0.00" rel $RES econ_lam0 0.0 rel_v9_econ_cv00.json &
run_soft "reliability econ cv 0.20" rel $RES econ_lam0 0.20 rel_v9_econ_cv20.json &
run_soft "reliability econ cv 0.40" rel $RES econ_lam0 0.40 rel_v9_econ_cv40.json &
run_soft "reliability FFH-free cv 0" rel $RES eps_0.00 0.0 rel_v9_zero_cv00.json &
run_soft "soft heat balance and VSS" env ROUTE_INPUTS=$IN CAMP_OUT=evpi_vss_results_v9.json \
    CAMP_LOGDIR=logs_v9 EVPI_SRC=$RES EVPI_OUT=evpi_vss_v9.json CAMP_THREADS=8 "$PY" evpi_vss_run.py &
for f in ieee_figs/fig6_*; do [ -e "$f" ] && cp -n "$f" "${f%.*}_v8.${f##*.}"; done 2>/dev/null
run_soft "severe-day figure" env ROUTE_INPUTS=$IN FIG6_RES=$RES "$PY" ieee_fig6.py &
wait
run_soft "merge econ reliability" "$PY" - <<'EOF'
import json
parts = ["rel_v9_econ_cv00.json", "rel_v9_econ_cv20.json", "rel_v9_econ_cv40.json"]
out = None
for fn in parts:
    d = json.load(open(fn))
    if out is None:
        out = d
    else:
        out["levels"].update(d["levels"])
        out["minutes"] = round(out.get("minutes", 0) + d.get("minutes", 0), 1)
out["note_v9"] = ("heat CV levels run as three processes with the same seed "
                  "(draw streams restart per level)")
json.dump(out, open("rel_v9_econ_full.json", "w"), indent=1)
print("levels:", list(out["levels"]))
EOF
run_soft "provenance" env PROV_RES=$RES PROV_OUT=provenance_v9.json PROV_LOGDIR=logs_v9 "$PY" make_provenance_v5.py
run_soft "integrity checks" env ROUTE_INPUTS=$IN CHECK_RES=$RES CHECK_PROV=provenance_v9.json "$PY" check_results_v5.py
) > lanes_v9/post.log 2>&1
echo "=== Route 52 post-processing done === $(date)"
touch ROUTE52_V9_DONE

# ---------------- wait for follow-ups/add-ons ------------------------------
wait $P_R100 $P_CA $P_CB $P_CC
while alive "rel_v9_relmatch_eps0_r75" || alive "route52_inputs_v9_fuel115"; do sleep 120; done
echo "=== follow-ups and add-ons done === $(date)"
touch ADDONS_V9_DONE

# ---------------- division: merge A, then stability after D ----------------
wait $P_DA
while alive "campaign_division_v5.py D"; do sleep 120; done
(
run_soft "merge division A" "$PY" - <<'EOF'
import json
d = json.load(open("campaign_division_v9.json"))
a = json.load(open("campaign_division_v9_A.json"))
d["cases"]["A_fragmented"] = a["cases"]["A_fragmented"]
json.dump(d, open("campaign_division_v9.json", "w"), indent=1)
print("cases:", list(d["cases"]))
EOF
run_soft "division stability" env $DIVENV DIV_OUT=$DIV DIV_THREADS=18 "$PY" campaign_division_v5.py stability
) > lanes_v9/division2.log 2>&1
echo "=== division done === $(date)"
touch DIVISION_V9_DONE
echo "=== v9 complete === $(date)"
grep -h '!!!' lanes_v9/*.log || echo "all stages OK"
