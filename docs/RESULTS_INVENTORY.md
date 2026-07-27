# Results inventory — v6 campaign

Status key: **certified** = absolute gap <= 1 kCAD; **loose** = above it,
queued for `refine_v6.py`; **pending** = not yet produced.

## Baseline and policy

| run | F1 kCAD/yr | abs gap CAD | CO2 t/yr | fleet | status |
|---|---|---|---|---|---|
| `econ_lam0` | 2,372.2 | 982 | 27.30 | 18xstd-FFH | certified |
| `policy_lam100` | 2,371.7 | 548 | 25.81 | 18xstd-FFH | certified |
| `policy_lam100_ops` | 2,371.9 | 794 | 26.31 | 18xstd-FFH | certified |

## Emissions-cap frontier

| run | F1 kCAD/yr | abs gap CAD | CO2 t/yr | fleet | status |
|---|---|---|---|---|---|
| `eps_1.00` | 2,372.2 | 450 | 25.79 | 18xstd-FFH | certified |
| `eps_0.70` | 2,375.4 | 1,868 | 12.23 | 18xstd-FFH | **loose** |
| `eps_0.50` | 2,375.2 | 150 | 8.68 | 18xstd-FFH | certified |
| `eps_0.35` | 2,375.4 | 681 | 8.65 | 18xstd-FFH | certified |
| `eps_0.20` | 2,384.1 | 2,187 | 4.84 | 14xstd-FFH, 4xext-eOnly | **loose** |
| `eps_0.10` | 2,394.1 | 7,016 | 0.92 | 4xstd-FFH, 14xstd-eOnly | **loose** |
| `eps_0.00` | 2,404.5 | 1,720 | 0.00 | 13xstd-eOnly, 5xext-eOnly | **loose** |

## Carbon-price sweep

| run | F1 kCAD/yr | abs gap CAD | CO2 t/yr | fleet | status |
|---|---|---|---|---|---|
| `lam_200` | 2,374.7 | 559 | 9.59 | 18xstd-FFH | certified |
| `lam_500` | 2,374.9 | 655 | 9.06 | 18xstd-FFH | certified |
| `lam_1000` | 2,374.9 | 892 | 9.10 | 18xstd-FFH | certified |
| `lam_2000` | 2,380.4 | 2,030 | 6.26 | 16xstd-FFH, 2xext-eOnly | **loose** |
| `lam_3500` | 2,399.0 | 6,481 | 0.31 | 4xstd-FFH, 13xstd-eOnly, 1xext-eOnly | **loose** |
| `lam_5000` | 2,394.4 | 999 | 0.65 | 4xstd-FFH, 14xstd-eOnly | certified |
| `lam_10000` | 2,395.5 | 2,339 | 0.51 | 3xstd-FFH, 14xstd-eOnly, 1xext-eOnly | **loose** |

## Breakpoint verification

| run | F1 kCAD/yr | abs gap CAD | CO2 t/yr | fleet | status |
|---|---|---|---|---|---|
| `bp_lam_241` | 2,374.8 | 988 | 9.75 | 18xstd-FFH | certified |
| `bp_lam_2309` | 2,384.0 | 5,702 | 4.90 | 14xstd-FFH, 4xext-eOnly | **loose** |
| `bp_lam_2535` | 2,380.5 | 6,330 | 6.85 | 16xstd-FFH, 2xext-eOnly | **loose** |

## Value of stochastic planning

| run | F1 kCAD/yr | abs gap CAD | CO2 t/yr | fleet | status |
|---|---|---|---|---|---|
| `det_meanT` | 2,349.2 | 955 | 0.00 | 18xstd-eOnly | certified |
| `det_design_full_test` | — | — | — | — | infeasible (status 3) |
| `frozen_z` | 2,372.0 | 954 | 26.38 | 18xstd-FFH | certified |
| `n_minus_1` | 2,383.5 | 374 | 73.59 | 18xstd-FFH | certified |

## Cost sensitivities

| run | F1 kCAD/yr | abs gap CAD | CO2 t/yr | fleet | status |
|---|---|---|---|---|---|
| `ffh_om_500` | 2,362.7 | 548 | 25.81 | 18xstd-FFH | certified |
| `ffh_om_2000` | 2,389.7 | 983 | 25.81 | 18xstd-FFH | certified |
| `ffh_capex_5000` | 2,382.1 | 826 | 26.23 | 18xstd-FFH | certified |
| `ffh_capex_15000` | — | — | — | — | pending |
| `batt_100` | 2,371.7 | 801 | 25.82 | 18xstd-FFH | certified |
| `batt_50` | 2,373.1 | 953 | 9.04 | 7xstd-FFH, 11xext-eOnly | certified |
| `grid_100` | 2,369.8 | 652 | 25.96 | 18xstd-FFH | certified |
| `grid_300` | 2,373.7 | 617 | 25.90 | 18xstd-FFH | certified |

## Physical sensitivities

| run | F1 kCAD/yr | abs gap CAD | CO2 t/yr | fleet | status |
|---|---|---|---|---|---|
| `derate_mild` | 2,370.8 | 860 | 17.70 | 17xstd-FFH, 1xstd-eOnly | certified |
| `derate_harsh` | 2,371.7 | 548 | 25.81 | 18xstd-FFH | certified |
| `reserve_25` | 2,371.7 | 551 | 25.82 | 18xstd-FFH | certified |
| `reserve_50` | 2,373.4 | 890 | 29.25 | 18xstd-FFH | certified |
| `precond_tau_0.25` | 2,372.8 | 991 | 27.77 | 18xstd-FFH | certified |
| `precond_tau_1.0` | 2,371.2 | 550 | 25.33 | 18xstd-FFH | certified |

## Fleet sensitivities

| run | F1 kCAD/yr | abs gap CAD | CO2 t/yr | fleet | status |
|---|---|---|---|---|---|
| `spare_15` | 2,829.9 | 12,117 | 9.55 | 22xstd-FFH | **loose** |

## Out-of-sample reliability (Route 52, carbon-price design, N=1000/band)

| stress level | P(winter day fully served) | E[shortfall] kWh/winter | severe band |
|---|---|---|---|
| empirical traction only | **0.982** | 16.5 | 0.889 |
| + heat CV 0.20 (declared) | 0.976 | 69.2 | 0.771 |
| + heat CV 0.40 (declared) | 0.864 | 2,580.6 | 0.274 |

Traction residual pool: 1,377 Route 52 bus-days against the leave-Route-52-out
fit — mean ratio 1.0059, sd 0.079, p05–p95 0.887–1.135. Essentially unbiased
out of sample.

Reserve-50 operating policy, same design, judged on the common SoC floor: in progress.

## Division scale (14 routes, 183 blocks)

| case | differentiating cost kCAD | abs gap | FFH share | status |
|---|---|---|---|---|
| A fragmented | — | — | — | in progress (10/14 routes) |
| B route-locked | 2,760.7 | 248,766 | 55% | **superseded** — re-solving warm-started |
| C shared pool, frozen | 2,715.1 | 210,311 | 25% | **superseded** — re-solving warm-started |
| D full coordination | 2,784.9 | 279,696 | 26% | **superseded** — cost above C is impossible |
| near-optimal stability | — | — | — | pending corrected D |

The first pass is not usable: D's feasible set contains C's, so D cannot cost
more. The ordering was an artifact of gaps an order of magnitude larger than
the coordination effect. A rigorous claim needs D's incumbent below C's lower
bound.
