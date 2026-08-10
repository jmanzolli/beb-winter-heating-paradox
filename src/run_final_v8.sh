#!/bin/bash
# Remaining v8 work after stages 0-4 completed. Replaces the tail of
# run_all_v8.sh (stage 5) and run_post_v8.sh, both of which were stopped:
#
#   1. econ_lam0 re-solve, lexicographic          (fixes the baseline)
#   2. batt_50 sensitivity                        (brackets the pack price)
#   3. division D warm-started from C, then A     (B and C dropped)
#   4. provenance_v8.json                         (last, so it sees 1-2)
#
# Division scope: only A (fourteen independent route optima, which supplies the
# certified bound) and D (full coordination) are needed. C is already solved and
# is kept solely as D's warm start -- D's own incumbent, 2,899.7, is worse than
# C's 2,827.4, the same time-limit artefact seen in the v7 first round, and
# without the warm start the certified saving can come out negative. B is not
# run at all; the near-optimal stability table loses its route-locked point.
#
# Usage:  nohup ./run_final_v8.sh > final_v8.log 2>&1 &
cd "$(dirname "$0")"
PY=${PY:-$HOME/grbenv/bin/python}
[ -x "$PY" ] || PY=python3
export GRB_LICENSE_FILE=${GRB_LICENSE_FILE:-$HOME/gurobi.lic}

THREADS=${THREADS:-28}
MEMGB=${MEMGB:-96}
RES=campaign_v8_results.json
DIV=campaign_division_v8.json

FAILED=""
run_soft () {
  local name="$1"; shift
  echo "=== $name ==="
  if "$@"; then echo "--- $name OK"
  else echo "!!! $name FAILED -- continuing" >&2; FAILED="${FAILED}${name}; "; fi
}

echo "host $(hostname) | threads $THREADS | started $(date)"

run_soft "1. econ_lam0 lexicographic re-solve" \
  env ROUTE_INPUTS=route52_inputs_v7.json CAMP_OUT=$RES \
      CAMP_THREADS=$THREADS CAMP_MEM_GB=$MEMGB CAMP_NODEFILE_GB=16 \
      "$PY" econ_lex_run.py

run_soft "2. batt_50 sensitivity" \
  env ROUTE_INPUTS=route52_inputs_v7.json CAMP_OUT=$RES \
      CAMP_THREADS=$THREADS CAMP_MEM_GB=$MEMGB \
      "$PY" batt50_run.py

# D first (the script runs D before A regardless of argument order), warm-started
# from the better C incumbent; then A's fourteen per-route solves.
run_soft "3. division D (warm-started from C) then A" \
  env ROUTE_INPUTS=garage_inputs_v7.json DIV_OUT=$DIV DIV_LOGDIR=logs_div_v8 \
      DIV_THREADS=$THREADS DIV_MEM_GB=$MEMGB DIV_NODEFILE_GB=16 \
      DIV_START_FROM=$DIV:C_shared_infra_frozen_z \
      "$PY" campaign_division_v5.py D A

echo "=== 4. provenance_v8 ==="
PROV_RES=$RES PROV_OUT=provenance_v8.json PROV_LOGDIR=logs_v5 \
  "$PY" make_provenance_v5.py

echo "=== done $(date) ==="
[ -n "$FAILED" ] && echo "SOFT-FAILED: $FAILED" || echo "all steps OK"
