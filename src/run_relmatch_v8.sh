#!/bin/bash
# Reliability-matched premium for full heating electrification.
#
#   Stage A: re-select the FFH-free design at planning reserves
#            Gamma = 25, 50, 75, 100 kWh (base is 10).
#   Stage B: evaluate each design out of sample at the STANDARD judging
#            requirement, so its reserve compliance is comparable with the
#            baseline's 99.62%. REL_RESERVE is deliberately NOT set: judging a
#            reserve-75 design against a 75 kWh requirement would measure a
#            different quantity.
#
# The premium that matters is then F1(smallest Gamma reaching 99.62%) minus the
# baseline's F1, rather than the +48.8 kCAD/yr that compares designs of
# different reliability.
#
# Usage:  nohup ./run_relmatch_v8.sh > relmatch_v8.log 2>&1 &
set -e
cd "$(dirname "$0")"
PY=${PY:-$HOME/grbenv/bin/python}
[ -x "$PY" ] || PY=python3
export GRB_LICENSE_FILE=${GRB_LICENSE_FILE:-$HOME/gurobi.lic}
THREADS=${THREADS:-28}
RES=relmatch_v8.json

echo "host $(hostname) | threads $THREADS | started $(date)"

echo "=== stage A: FFH-free designs at raised planning reserve ==="
ROUTE_INPUTS=route52_inputs_v7.json CAMP_OUT=$RES \
CAMP_THREADS=$THREADS CAMP_MEM_GB=${MEMGB:-96} CAMP_NODEFILE_GB=16 \
  "$PY" relmatch_run.py

echo "=== stage B: out-of-sample reliability of each design ==="
for G in 25 50 75 100; do
  L=relmatch_eps0_r${G}
  echo "--- $L"
  ROUTE_INPUTS=route52_inputs_v7.json REL_RESULTS=$RES \
  REL_DESIGN=$L REL_LAM=0 REL_HEAT_CVS=0.0 \
  REL_POOL=v7_residual_pool.json REL_OUT=rel_v8_${L}.json \
    "$PY" reliability_v5.py 1000 || echo "!!! $L reliability FAILED" >&2
done

echo "=== done $(date) ==="
