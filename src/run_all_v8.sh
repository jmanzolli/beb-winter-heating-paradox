#!/bin/bash
# v8 re-run: updated Paper 1 posterior (rev. Aug 2026) + CAD-corrected costs.
# Sequential: a WLS licence with a single-session limit never sees two Gurobi
# sessions, so every stage runs one after the other.
# Usage:  nohup ./run_all_v8.sh > run_all_v8.log 2>&1 &
#
# Stage order puts everything Route 52 (RQ1-RQ3) ahead of the division run, so
# the bulk of the manuscript can be regenerated while the long division solve
# is still going.
#
# Stages 1 and 5 resume: campaign_v5.solve() skips any label already recorded
# in CAMP_OUT/DIV_OUT, so re-launching after a kill costs only the run that was
# in flight.
#
# Stages 2-4 are diagnostics that feed Fig. 3(b), Fig. 5 and the reliability
# rows. They are independent of each other and of the division run, so a
# failure in one is reported and the chain continues -- otherwise a crash in a
# post-processing step would take the 12 h division solve down with it. The two
# solve stages keep fail-fast semantics.
set -e
cd "$(dirname "$0")"
mkdir -p logs_v5 logs_div_v8

# interpreter: the INESC server keeps gurobipy in ~/grbenv (system python3 is
# 3.6 without it); fall back to python3 elsewhere.
PY=${PY:-$HOME/grbenv/bin/python}
[ -x "$PY" ] || PY=python3
export GRB_LICENSE_FILE=${GRB_LICENSE_FILE:-$HOME/gurobi.lic}

NCPU=$(nproc 2>/dev/null || sysctl -n hw.ncpu)
THREADS=${THREADS:-28}; [ "$THREADS" -gt "$NCPU" ] && THREADS=$(( NCPU - 2 ))
MEMGB=${MEMGB:-96}

RES=campaign_v8_results.json
DIV=campaign_division_v8.json

echo "host $(hostname) | ${NCPU} cores | ${THREADS} threads | mem limit ${MEMGB} GB | py $PY"

# licence probe (fail fast, same idea as run_division.sh)
"$PY" - <<'EOF'
import gurobipy as gp
m = gp.Model()
m.addVar()
m.update()
print("licence OK:", gp.gurobi.version())
EOF

# a diagnostic stage that must not abort the chain
run_soft () {
  local name="$1"; shift
  echo "=== $name ==="
  if "$@"; then
    echo "--- $name OK"
  else
    echo "!!! $name FAILED (exit $?) -- continuing" >&2
    FAILED_STAGES="${FAILED_STAGES}${name}; "
  fi
}
FAILED_STAGES=""

echo "=== stage 0: model self-checks (v8) ==="
ROUTE_INPUTS=route52_inputs_v7.json "$PY" test_v5.py

echo "=== stage 1: Route 52 campaign (v8) ==="
ROUTE_INPUTS=route52_inputs_v7.json CAMP_OUT=$RES \
CAMP_THREADS=$THREADS CAMP_MEM_GB=$MEMGB CAMP_NODEFILE_GB=16 \
"$PY" campaign_v5.py

# --- stage 2: per-scenario operating record for the ECONOMIC baseline -------
# Fig. 3 panels (a) and (b) must describe the same design; without this the
# margins come from the lambda=100 run and the heat shares from econ_lam0.
# Writes ops_metrics_econ back into $RES.
run_soft "stage 2: econ_lam0 ops record (v8)" \
  env ROUTE_INPUTS=route52_inputs_v7.json CAMP_OUT=$RES \
      CAMP_THREADS=$THREADS CAMP_MEM_GB=$MEMGB \
      "$PY" v7_econ_ops.py

# --- stage 3: per-band feasibility of the mean-temperature benchmark --------
# Fig. 5(a) and the "benchmark survives only the mild band" claim in IV-B.
run_soft "stage 3: det-benchmark per-band check (v8)" \
  env ROUTE_INPUTS=route52_inputs_v7.json \
      DETBAND_RES=$RES DETBAND_OUT=detband_v8.json \
      "$PY" detband_check.py

# --- stage 4: out-of-sample reliability -------------------------------------
# 1000 draws per winter band = the 5,000 the manuscript reports. REL_LAM=0 for
# both designs: each is evaluated under the objective it was built with (the
# baseline minimises F1, the zero design minimises F1 under a cap), so the two
# columns are comparable. REL_POOL loads the precomputed traction-residual pool
# so the TTC workbook is not needed on the solve host.
#
# Economic baseline gets all three cabin-heat stress levels (0 / 0.20 / 0.40);
# the design COMPARISON in Table IV and Fig. 5(b) uses cv = 0 alone.
run_soft "stage 4a: reliability, economic baseline, cv 0/0.20/0.40 (v8)" \
  env ROUTE_INPUTS=route52_inputs_v7.json REL_RESULTS=$RES \
      REL_DESIGN=econ_lam0 REL_LAM=0 REL_HEAT_CVS=0.0,0.20,0.40 \
      REL_POOL=v7_residual_pool.json REL_OUT=rel_v8_econ_full.json \
      "$PY" reliability_v5.py 1000

run_soft "stage 4b: reliability, full-electrification design, cv 0 (v8)" \
  env ROUTE_INPUTS=route52_inputs_v7.json REL_RESULTS=$RES \
      REL_DESIGN=eps_0.00 REL_LAM=0 REL_HEAT_CVS=0.0 \
      REL_POOL=v7_residual_pool.json REL_OUT=rel_v8_zero_cv00.json \
      "$PY" reliability_v5.py 1000

echo "=== stage 5: division cases D C B A + stability (v8) ==="
ROUTE_INPUTS=garage_inputs_v7.json DIV_OUT=$DIV \
DIV_LOGDIR=logs_div_v8 \
DIV_THREADS=$THREADS DIV_MEM_GB=$MEMGB DIV_NODEFILE_GB=16 \
"$PY" campaign_division_v5.py D C B A stability

echo "=== v8 runs complete ==="
if [ -n "$FAILED_STAGES" ]; then
  echo "SOFT-FAILED STAGES: $FAILED_STAGES"
else
  echo "all stages OK"
fi
echo
echo "Pull back to code/, then regenerate with:"
echo "  ROUTE_INPUTS=route52_inputs_v7.json \\"
echo "  TAB_RES=$RES TAB_DIV=$DIV TAB_PROV=provenance_v8.json \\"
echo "  TAB_REL_BASE=rel_v8_econ_full.json TAB_REL_ZERO=rel_v8_zero_cv00.json \\"
echo "  python3 make_tables_v6.py"
echo "  (same TAB_*/FIG_* convention for make_supp_tables.py and make_fig_m.py;"
echo "   make_fig_m.py also needs FIG_DETBAND=detband_v8.json)"
