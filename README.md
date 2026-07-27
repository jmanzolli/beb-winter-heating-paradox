# Zero-Emission Heating Paradox — reproduction package

Code, inputs, results and solver logs for:

> **The Zero-Emission Heating Paradox: Stochastic Planning and Operation of
> Electric Bus Fleets in Cold Climates**

A two-stage stochastic MILP that jointly selects bus heating and battery
specifications, charging infrastructure, terminal activation and grid capacity
for a fixed block schedule, with weather-dependent operational recourse.

## Data availability

The optimization code, processed non-confidential inputs, solver logs and all
result files are in this repository. **Raw TTC telemetry is not redistributed**
under the data-use agreement covering it. The empirical models it produced are
reproduced in full: the traction-interface coefficients are in
`configs/*.json`, and the cabin-thermal coefficients are tabulated in the
paper's supplementary material. Every optimization result here can therefore
be regenerated without the raw telemetry; only re-fitting the empirical
models from scratch requires it.

## Layout

| Path | Contents |
|---|---|
| `src/` | model, campaigns, reliability harness, table and figure generators |
| `configs/` | Route 52 and Arrow Road division instances, ECCC weather data |
| `results/` | every campaign result file, provenance, reliability output |
| `logs/` | archived Gurobi logs for all runs (`solver_logs.tar.gz`) |
| `tables/` | generated LaTeX tables for the paper and supplement |
| `figures/` | generated figures |
| `docs/` | audit, changelog, results inventory, data sources |

## Requirements

Python 3.9+, `gurobipy` 11.0.3 with a licence, plus `numpy` and `pandas` for
the reliability harness and the input fitting.

```bash
python3 -m venv venv && . venv/bin/activate
pip install "gurobipy==11.0.3" numpy pandas
```

## Reproducing the results

Run from `src/` with the config directory on the input path.

```bash
export ROUTE_INPUTS=../configs/route52_inputs_v5.json

python3 test_v5.py                 # formulation unit checks
python3 campaign_v5.py             # Route 52 campaign
python3 sens_v6.py cost physical ops   # sensitivity block (parallelizable)
python3 refine_v6.py               # warm-started refinement of loose runs
python3 reliability_v5.py 1000     # out-of-sample reliability
python3 check_results_v5.py        # automated integrity checks
```

Division scale:

```bash
export ROUTE_INPUTS=../configs/garage_inputs_v5.json
python3 campaign_division_v5.py D C B A
python3 rerun_div_v6.py            # warm-started C -> D -> B
python3 tighten_A_v6.py 250 3600   # tighten the per-route subproblems
```

Tables and figures:

```bash
python3 make_tables_v6.py
python3 make_supp_tables.py
python3 figdata_v6.py && FIG_CAMPAIGN=campaign_results_v6.json python3 ieee_figures.py
python3 ieee_fig6.py
```

## Verification

`check_results_v5.py` is the audit entry point. It verifies scenario weights
sum to 365 days, diesel and emissions accounting, that cost components sum to
$F_1$, that carbon payments are excluded from $F_1$, cap satisfaction, fleet
coverage, gap consistency, relaxation and carbon-price monotonicity, the
heater-rating bound on preconditioning, and that removed analyses do not
reappear in the manuscript.

## Notes on the formulation

Two corrections matter for anyone comparing against earlier versions.
Preconditioning power is bounded by the **electric heater's rated output**,
not by the charging acceptance — the earlier bound allowed several times the
rated output through the cabin heater. And preconditioning heat carries a
thermal-retention coefficient rather than being credited in full at departure.
Both are documented in `docs/REVISION_AUDIT.md`.

Frontier points are solved lexicographically: phase 1 certifies minimum cost,
phase 2 minimizes emissions subject to that cost plus a slack of 0.5 kCAD/yr.
Reported designs are the phase-2 solutions, whose cost may exceed the phase-1
certified incumbent by at most that slack.

## Licence

Code released under the MIT Licence. Result files and figures are released
under CC BY 4.0.
