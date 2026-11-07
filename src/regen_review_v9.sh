#!/bin/bash
# Regenerate every table and figure of the revised manuscript (review runs of
# 2026-11-06 merged into the v9 archive).
#   DATA  directory holding the configs and result files (default: v9rev)
#   OUT   directory receiving tables_v6/ and supp_tables/ (default: ../overleaf-git)
# Figures go to ieee_figs/ (and ../overleaf-git/figures if that exists).
set -e
cd "$(dirname "$0")"
DATA=${DATA:-v9rev}; OUT=${OUT:-../overleaf-git}
OUT=$(mkdir -p "$OUT/supp_tables" && cd "$OUT" && pwd)
HERE=$(pwd)
( cd "$DATA"
  export PYTHONPATH="$HERE" ROUTE_INPUTS=route52_inputs_v9.json TAB_NO_REV=1
  export TAB_TEXDIR="$OUT" TAB_TEXDIR_SUPP="$OUT/supp_tables"
  export TAB_RES=campaign_v9rev_results.json TAB_DIV=campaign_division_v9rev.json TAB_PROV=provenance_v9rev.json
  export TAB_REL_BASE=rel_v9rev_econ_full.json TAB_REL_ZERO=rel_v9rev_zero_cv00.json
  export SUPP_REL_BASE=$TAB_REL_BASE SUPP_REL_ZERO=$TAB_REL_ZERO SUPP_REL_FULL=$TAB_REL_BASE SUPP_REL_ZERO_FULL=rel_v9rev_zero_full.json
  export SUPP_CALIB=calib_chargers_v9.json SUPP_RELMATCH=relmatch_v9.json SUPP_VER=v9rev
  export TAB_DESIGNS=econ_lam0,eps_0.70,eps_0.20,lam_5000,eps_0.00,det_meanT
  python3 "$HERE/make_tables_v6.py" && python3 "$HERE/make_supp_tables.py" )
export PYTHONPATH="$HERE"
FIG_RES=$DATA/campaign_v9rev_results.json FIG_DIV=$DATA/campaign_division_v9rev.json FIG_DETBAND=$DATA/detband_v9rev.json \
FIG_REL_BASE=$DATA/rel_v9rev_econ_full.json FIG_REL_ZERO=$DATA/rel_v9rev_zero_full.json ROUTE_INPUTS=$DATA/route52_inputs_v9.json \
  python3 make_fig_m.py
V9_DIR=$DATA V9_INPUTS=$DATA/route52_inputs_v9.json V9_WEATHER=${V9_WEATHER:-data_v9/eccc_winter_bands_v9.json} \
V9_DIV=$DATA/campaign_division_v9rev.json python3 make_figs_v9extra.py
