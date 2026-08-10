# Revision changelog (T-ITS revision protocol, deliverable 7)

Status legend: **done** — code, results and manuscript all updated and
verified; **awaiting results** — code and manuscript updated, verification
pending the v6 campaign; **pending** — not yet started.

| # | Issue | Original problem | Correction made | Code files changed | Equations changed | Experiments rerun | Manuscript sections | Final verification |
|---|---|---|---|---|---|---|---|---|
| 1 | Preconditioning bypassed the heater rating | `p^pre` bounded only by charging acceptance (450 kW) and charger rating; up to 40 kW pushed through a 23 kW heater in one step, and the bound was **active** at the v5 optimum | Added `p^pre ≤ Σ_κ P^el_κ z_{b,κ}` | `route52_prototype.py` | new `(eq:preplug-d)` | all Route 52 runs | III-C | `test_v5.py` peak `p^pre` = 23.00 kW in every heated scenario; measured effect +269 CAD/yr on the fixed policy design (`test_ppre_rating.json`) — awaiting results |
| 2 | Preconditioning credited at full value | Delivered depot preheat credited to trip 1 at χ = 1, capped only at 10 kWh; heat delivered an hour before pull-out counted as fully retained | Split delivered heat from credited heat; χ_{b,t} = exp(−(t_dep − t)/τ), τ = 0.5 h, swept at 0.25 and 1.0 h | `route52_prototype.py`, `campaign_v5.py` | `(eq:preq-a)`, `(eq:preq-b)`, `(eq:precredit)`, `(eq:heat)` | all Route 52 runs + new τ sensitivity | III-C | credit ≤ delivered verified per block in `test_v5.py`; baseline CO₂ moved 24.18 → 27.30 t/yr, the expected direction — awaiting results |
| 3 | α_{b,i} untyped | Read as a decision variable in the manuscript, making α·q^pre bilinear; was a fixed allocation in code | Declared a fixed parameter (α_{b,1} = 1) in the notation table and in the text | — (code already correct) | `(eq:precredit)` replaces `(eq:precredit-a/b)` | none | III-C, Table I | manuscript states the allocation and the absence of bilinearity — **done** |
| 4 | Plug exclusivity only partial | `u + u^pre ≤ 1` enforced at the depot only; nothing prevented occupancy at two sites | `Σ_n u_{b,n,t} + u^pre_{b,t} ≤ 1` for every bus and step | `route52_prototype.py` | `(eq:charging-e)` | all Route 52 runs | III-F | `test_v5.py` single-plug check, 0 violations in all scenarios — awaiting results |
| 5 | Charger-class index inconsistent | `u_{b,dep,t}` and `u_{b,n,t,p}` used interchangeably; Remark 1 collapsed the index only "in implementation" | Collapsed the class index in the formulation itself, justified by one active class per site | — | `(eq:charging-a…e)`, `(eq:opex)`, `(eq:recovery)`, `(eq:cyclic-b)`, `(eq:siteload)` | none | III-F, Table I | notation now matches the implementation one-to-one — **done** |
| 6 | Heater output limits undocumented | Rated-output constraints existed in code (v5) but appeared nowhere in the manuscript; `Qbar_{i,m}(ω)` was never defined | Added rated-output equations; replaced `Qbar` with the delivered demand it always equalled | — | new `(eq:heatlimits-a/b)`, `(eq:ffhavail)` restated | none | III-C | equations match `route52_prototype.py` lines 394–396 — **done** |
| 7 | Big-M claim was false | Manuscript stated class-dependent SoC limits use big-M deactivation; code uses the exact linear form, valid because Σ z = 1 | Deleted `(eq:bigM)` and replaced it with the exactness argument | — | `(eq:bigM)` removed | none | III-D | integrity check 25e scans for any surviving big-M claim — **done** |
| 8 | Valid inequalities claimed but absent | Three families stated; none implemented, and the grid-energy bound predates the EVSE correction | Removed both stated inequalities rather than retaining an underived cut | — | `(eq:cut-energy)`, `(eq:cut-deficit)` removed | none | IV-B | no valid inequalities are claimed; results use the deterministic equivalent directly — **done** |
| 9 | Dimensionally weak augmented ε | `min F1 − δξ/r₂` mixes a monetary objective with a dimensionless term that can fall below solver tolerance | Lexicographic two-phase ε-constraint: certify cost, then minimize emissions under a cost cap | `campaign_v5.py` | `(eq:augmecon)` → `(eq:lexeps)`, Algorithm 1 rewritten | full frontier | III-G, IV-A | both phases logged separately per point — awaiting results |
| 10 | "Annual" cost over a 151-day horizon | Annualized capital combined with winter-only operating cost and reported as annual system cost | Added a heat-free off-season scenario (214 d at +17.4 °C) so Σ h_ω = 365 | `fit_v5_inputs.py` | `(eq:objectives-a)` | all runs | II-B, III-G, V | `test_v5.py` weights_sum_365; off-season diesel and heat both zero — awaiting results |
| 11 | Demand charge under-specified | `Ω_ℓ`, the number of billed months, and winter vs non-winter treatment were never defined | Two billing periods with explicit month multipliers M_win = 5, M_off = 7 | `route52_prototype.py` | `(eq:grid-b)`, `(eq:objectives-a)` | all runs | III-F | formulation matches the implementation; described as a conservative representative-day approximation — **done** |
| 12 | Circular validation | Traction model fitted on all routes including Route 52, then "validated" against Route 52 diesel use | Route 52 instance uses a leave-Route-52-out fit (1,377 runs removed); agreement relabelled calibration consistency | `fit_v5_inputs.py` | — | all Route 52 runs | II-B, App. B, VI, VII | both coefficient sets reported; no claim of independent validation survives — **done** for the wording, awaiting results for the comparison |
| 13 | Residual uncertainty not propagated | Weather scenarios carry temperature only; conditional-mean feasibility presented as service reliability | Out-of-sample harness: empirical block-day traction residuals, declared cabin-heat stress levels, design and day-ahead assignment fixed, penalized shortfall | `reliability_v5.py` | — | new experiment | VI-B, VII | queued in the run chain — **awaiting results** |
| 14 | Coordination inferred across different systems | Route 52 vs Arrow Road compared two different route sets | Four same-system cases A–D on the 14-route division, isolating shared infrastructure, shared pool, and adaptive assignment | `campaign_division_v5.py` | — | new experiment | V-C, VI-D | queued in the run chain — **awaiting results** |
| 15 | Division gap dominated by constant cost | 183 identical base buses dominate the objective, making the relative gap meaningless | Differentiating-cost objective with the base cost added back only for reporting; case A put on the same basis | `route52_prototype.py`, `campaign_division_v5.py` | — | division cases | V-C | gaps reported against differentiating cost — awaiting results |
| 16 | Single design reported as definitive | One equipment count reported although many are near-optimal | Min/max FFH buses, opportunity chargers, and extended batteries under a cost tolerance | `campaign_division_v5.py` | — | new experiment | VI-D, VII | queued in the run chain — **awaiting results** |
| 17 | Fleet-size claims implied | Introduction implied fleet expansion is an optimized alternative | Stated explicitly that the service plan is fixed, one bus per block, no splitting or swaps | — | — | none | I-A, I-C, VII | **done** |
| 18 | Heat-pump sensitivity | Constant-COP experiment and its 48.7 kCAD/yr result | Removed from experiment set and manuscript; the literature citation is retained | `campaign.py` (v4, superseded) | — | removed | IV-C, VI-C, VII | integrity checks 25a/25c scan the manuscript outside the related-work subsection — **done** |
| 19 | Scope 2 analysis | Ontario grid-intensity comparison | Removed; the environmental objective is onboard Scope 1 only | — | — | removed | IV-C, VI-C, VII | integrity check 25b — **done** |
| 20 | Solver logs not archived | `OutputFlag=0` suppressed file logging as well as console output, leaving 70-byte stubs for all 13 v5 runs | Console output off, file logging on | `campaign_v5.py` | — | all runs | App. C | v6 logs are 16–23 kB per run — **done** |
| 21 | Tables transcribed by hand | Tables IV and V typed from JSON | `make_tables_v6.py` emits every manuscript table from the result files, into both the code tree and `Overleaf/tables_v6/`; `main.tex` now `\input`s them, so no number is ever copied by hand | `make_tables_v6.py` | — | — | VI, App. C | Tables V and the computational table are generated and compile; the division and stability tables generate as soon as those cases land — **awaiting results** |
| 22 | Table IV column ambiguity | "Energy cost" did not distinguish electricity, diesel, and total operating cost | Table IV now reports electricity, diesel cost, and their sum labelled *total variable energy cost*, per representative day; annualized capital, demand charges and FFH O&M are excluded from it and reported in the cost decomposition instead | `make_tables_v6.py`, `campaign_v5.py` | — | all runs | VI | generator writes the split columns; needs the per-scenario record (`scen_ops`) — recovered by `refine_v6.py` — **awaiting results** |
| 24 | Charger counts hid their rating | Design tables summed depot chargers, so 8x100 kW and 3x300 kW appeared as "8" and "3" — different infrastructure reported as if comparable | Charger rows now report count x rating | `make_tables_v6.py` | — | — | VI | visible in the generated Table V — **done** |
| 23 | Preconditioning invisible in the archive | Records stored no preconditioning quantity, so defect 1 could not be detected without re-solving | Peak `p^pre`, annual preconditioning energy, and τ stored per run | `campaign_v5.py`, `check_results_v5.py` | — | all runs | — | integrity check 12 re-verifies the heater rating from the archive — awaiting results |

## v8 (2026-08-07): Paper 1 posterior refresh (rev. Aug 2026) + cost-currency fix

Basis-paper repository (Chogaliu/Zero-Emission-Paradox-of-Electric-Buses) was
re-estimated and reparameterized; every thermal input to the MILP changed.

- Demand coefficients (NF posterior medians): beta0 4.5130 -> 4.1121 kW,
  beta1 0.1839 -> 0.2694 kW/C, beta2 0.0009 -> 0.00208 kW/((km/h).C) with the
  motion term now CENTERED at v_ref = 15 km/h airspeed, beta3 -> 3.70e-5
  kWh/(stop.C) direct energy (e_door dropped), beta4 -> -0.0074 kWh/pax
  (e_pax dropped), beta5 -0.2023 -> -0.9275 kW. Cold-band demand rises
  ~15-19%.
- Useful-heating fraction: linear 0.5192 + 0.0054 T replaced by logit link
  logit^-1(0.3301 + 0.0117 T) (NF). phi 0.53-0.59 across winter bands.
- FFH useful output: fixed 12 kW replaced by scenario-dependent
  phi(T_w) x 35 kW nominal (18.6-20.6 kW). Inputs jsons now carry
  ffh_nominal_kw = 35; legacy ffh_rated_kw removed.
- Diesel accounting: DIESEL_LHV 9.96 kWh/L replaced by FFH_KWH_PER_L =
  35 kW / (3.6 kg/h / 0.837 kg/L) = 8.137 kWh nominal heat per liter,
  matching Paper 1's full-load burner convention.
- Costs: Paper 1 Appendix C states 1.0 MUSD/bus and 150 USD/kWh at
  FX 1.37 CAD/USD; BUS_BASE 1.00 -> 1.37 MCAD, BATT_COST 150 -> 205.5
  CAD/kWh. Battery sensitivity sweep now (150, 100, 300).
- Reporting fix: monthly_peak_kW in the CLI reporter indexed rho[n] after
  rho became (site, period); now takes the per-site max over periods.
- Reference-number updates in the manuscript: observed Route 52 FFH use
  10,149 -> 10,305 L; fleet FFH heat ~20 kW mean (13-26); 315 t CO2;
  31.5% of December operating energy intensity.

Re-run: `run_all_v8.sh` (Route 52 campaign -> campaign_v8_results.json, then
division -> campaign_division_v8.json).

### v8 addendum (2026-08-07): repository restructure

The short (10-page) manuscript is now the single master at `../Overleaf/`,
targeting IEEE TTE. The long draft, stale PDFs, LaTeX build artifacts and
v4/v6-era result files were moved (not deleted) to
`../_archive_2026-08-07/`; see its `ARCHIVE_MANIFEST.md`. Table and figure
generators were repointed from `../Overleaf/short/` to `../Overleaf/`:
`make_tables_v6.py`, `make_supp_tables.py`, `make_fig_m.py`,
`make_bandcal_table.py`, `make_traction_v7.py`.

The TTC telemetry workbook now lives at `code/data/` and
`reliability_v5.py` resolves it there (`TTC_XLSX` overrides).
