# Revision audit — reproducibility map and equation-to-code report

Scope: T-ITS revision protocol Sections 2, 3 and 11.1.
State of the project at the time of this audit: the model has already been
carried to **v5** (heater-rating limits, off-season scenario, billing-period
demand charges, plug-exclusivity guard, differentiating-cost objective,
lexicographic frontier). The **manuscript has not been touched**: it still
carries v4 numbers, the heat-pump sensitivity, and the Scope 2 analysis.

---

## 1. Reproducibility map

Working tree: `.../Bus Planning and Operation in Winter/code`
Empirical repo: `/Users/natomanzolli/Documents/GitHub/heating_system_study`

| Protocol item | File | Status |
|---|---|---|
| 1. Main optimization model | `route52_prototype.py` (`build_model`) | current (v5) |
| 2. Sets, parameters, variables | `route52_prototype.py` §1–2 | current; domains implicit in `vtype`, not documented in the manuscript |
| 3. Table III parameters | `route52_inputs_v5.json`, `garage_inputs_v5.json`, constants in `route52_prototype.py` §1, provenance in `DATA_SOURCES.md` | mixed: telemetry/GTFS/ECCC real; `SITE_FIXED_COST`, `GRID_EXISTING[depot]`, derate slopes are undocumented assumptions |
| 4. Thermal-demand coefficients | `route52_prototype.py` `B0..B5`, `phi_useful` — Paper 1 Table 4 posterior medians (New Flyer) | real, hard-coded (not read from the empirical repo) |
| 5. Traction coefficients | `fit_v5_inputs.py` → `traction` block of the input JSONs | real; Route 52 instance uses the **leave-Route-52-out** fit (R²=0.11, n=12,380), division instance uses the full-sample fit (R²=0.117, n=13,757) |
| 6. Weather scenarios and weights | `fit_v5_inputs.py`, `eccc_offseason_{2024,2025}.json`, `scenarios` block | real; 5 winter bands (151 d) + off-season (214 d, 17.4 °C, heat-free) = 365 d |
| 7. Route 52 blocks | `route52_prototype.py` `build_blocks()` from `branches` (GTFS-derived `route_summary.xlsx`) | real, 18 blocks |
| 8. Arrow Road division instance | `fit_garage_inputs.py` → `garage_inputs_v5.json` (27 branch entries, 14 routes, 183 blocks, 19 candidate sites) | real |
| 9. Tables IV / V | **no generator** — values were transcribed into `main.tex` by hand from v4 JSON | **defect**: protocol Section 6 requires programmatic generation |
| 10. Results figures | `ieee_figures.py`, `ieee_fig6.py`, `ieee_fig7_garage_map.py`, `ieee_fig8_garage_ops.py` → `ieee_figs/`, copied to `Overleaf/figures` | current visual design (do not redesign); data must be regenerated |
| 11. Carbon-price sweep | `campaign_v5.py` block C (`lam_*`, `bp_lam_*`) | current |
| 12. Epsilon frontier | `campaign_v5.py` block B, lexicographic two-phase | current |
| 13. Solver configuration | `campaign_v5.py` `_apply_limits` (MIPGapAbs 1000, TimeLimit 3600/7200, Threads 6, NodefileStart 1 GB, SoftMemLimit 11 GB) | current |
| 14. Solver logs / incumbents | `logs_v5/*.log`, `campaign_v5_results.json`, `provenance_v5.json` | **partial**: 13 of 13 first-pass runs have record-only provenance (the `OutputFlag=0` bug suppressed file logging); disclosed in `provenance_v5.json` |
| 15. Manual manuscript values | every number in `main.tex` Results/Abstract/Conclusions | all v4-era, all superseded |

### Reproducibility classification

**(a) Fully reproducible** — traction and off-season inputs (`fit_v5_inputs.py`),
block construction, scenario weights, the v5 solve itself, the integrity checks
(`check_results_v5.py`), the unit tests (`test_v5.py`).

**(b) Depends on manual processing** — Tables IV and V in the manuscript;
figure→table cross-consistency; the copy of figures into `Overleaf/figures`.

**(c) Manuscript values that do not match stored outputs** — all of them.
`main.tex` reports the v4 campaign (`campaign_results.json`, econ obj
2,260,173; zero-emission premium 28.4 kCAD/yr; heat-pump 48.7 kCAD/yr;
Scope 2 figures). The v5 campaign gives econ `F1` = 2,370,331 CAD/yr with a
365-day horizon. Nothing in Results/Abstract/Conclusions currently matches.

**(d) Missing files/data**
- Posterior predictive draws of the Paper 1 Bayesian thermal model — not
  archived; only the Table 4 posterior medians are available. Consequence:
  cabin-heat uncertainty in `reliability_v5.py` is a **declared parametric
  stress level**, not an empirical quantification (documented in that file).
- Metered FFH fuel per trip — does not exist in the telemetry. Same
  consequence.
- Non-heating auxiliary consumption per trip — not separable in the telemetry
  export; currently folded into the drivetrain fit.
- A published Toronto Hydro capital-contribution schedule — none exists;
  200 CAD/kW is a benchmark with a 100–300 sensitivity.

**(e) Code that must still change** — see Section 3 below.

---

## 2. Equation-to-code audit

Manuscript labels (`Overleaf/main.tex`), all linear unless noted.

| Label | Purpose | Units | Implemented? | Code | Correction required |
|---|---|---|---|---|---|
| `eq:capex` | annualized capital + FFH O&M | CAD/yr | yes | `route52_prototype.py:315` | none |
| `eq:opex` | scenario operating cost | CAD/day | yes | `:458` | none |
| `eq:siteclass-a/b/c` | one charger class, one grid tier per site | – | yes | `:307–310` | none |
| `eq:assign-a/b` | one class per block; fleet covers assignment | – | yes | `:357`, `:434` | none |
| `eq:loads-a` | class-dependent traction incl. mass penalty | kWh | yes | `:370` | none |
| `eq:loads-b` | class-dependent cabin-heat demand | kWh | **no** | `:366` | heat demand is class-independent (single vehicle type). Drop the class index or state `m` is a singleton |
| `eq:preplug-a` | precond ≤ bus acceptance | kW | yes | `:378` | — |
| `eq:preplug-b` | precond ≤ plug indicator | kW | yes | `:378` | — |
| **missing** | **precond ≤ electric heater rating** | kW | **no** | — | **C1, binding — see Section 3** |
| `eq:preplug-c` | depot plug count incl. precond | – | yes | `:449` | none |
| `eq:preq` | delivered precond heat | kWh | yes | `:374` | — |
| `eq:precredit-a/b` | trip-level precond credit via `α_{b,i}` | kWh | partly | `:375`, `:389` | `α` is a **fixed parameter** (=1 on trip 1, 0 otherwise) in code but reads as a variable in the manuscript. No thermal-retention coefficient χ. **C2** |
| `eq:heat` | cabin heat balance | kWh | yes | `:389` | — |
| `eq:ffhavail` | FFH only on FFH-equipped buses | kWh | yes | `:390` | define `Qbar_{i,m}(ω) := Q^use_{b,i}`, or drop as redundant with the rated bound |
| **v5 R1** | `q_el ≤ d·P_el`, `q_ffh ≤ d·P_ffh·z` | kWh | yes | `:394–396` | **not in the manuscript** — must be added |
| `eq:diesel` | diesel from FFH heat | L/day | yes | `:455` | — |
| `eq:capacity` | derated usable capacity | kWh | yes | `:358` | — |
| `eq:soc-a…e` | SoC dynamics, floor, ceiling, return reserve | kWh | yes | `:413–424` | — |
| `eq:recovery` | charge recovery in a dwell | kWh | yes | `:422` | — |
| `eq:bigM` | big-M class-dependent SoC limits | kWh | **no** | — | code uses the exact linear form `C_bω = δ·Σ C_k z_{b,κ}` (valid because `Σ z = 1`). The big-M paragraph is wrong and should be **deleted** |
| `eq:cyclic-a/b` | first departure and overnight closure | kWh | yes | `:413`, `:428` | — |
| `eq:charging-a…d` | plug power, availability, acceptance, plug count | kW | yes | `:399–400`, `:449` | class index collapsed per Remark 1 — correct |
| `eq:charging-e` | one plug per bus per step | – | **no** | — | structurally satisfied (dwell windows disjoint; verified by `test_v5.py`), but not enforced. **C3** |
| `eq:siteload` | site power incl. precond | kW | yes | `:444–448` | `L^fixed` is zero in the instance — state that |
| `eq:grid-a` | site power ≤ grid capacity | kW | yes | `:451` | — |
| `eq:grid-b` | billing peak ≥ site power | kW | yes | `:452` | manuscript must define `Ω_ℓ`: winter scenarios → 5 months, off-season → 7 months (`WINTER_MONTHS`, `OFFSEASON_MONTHS`) |
| `eq:objectives-a/b` | `F1` (no carbon), `F2` | CAD/yr, t/yr | yes | `:469`, `:465` | — |
| `eq:augmecon-a/b/c` | augmented ε-constraint | mixed | **no** | — | superseded: `campaign_v5.py:220–245` implements the **lexicographic** two-phase method. Manuscript must be rewritten (protocol 3.8) |
| `eq:cut-energy` | grid-energy valid inequality | kWh | **no** | — | not implemented, and its derivation predates the EVSE correction. **Remove from the manuscript** |
| `eq:cut-deficit` | class-elimination inequality | kWh | **no** | — | `Δ_b(ω)` never defined rigorously, no preprocessing code exists. **Remove** |
| Alg. 1 | frontier generation | – | partly | `campaign_v5.py` B + H | rewrite for the lexicographic method and the warm-started refinement pass actually used |

**Notation defects for the manuscript**: no variable-domain block; `u_{b,dep,t}`
vs `u_{b,n,t,p}` used inconsistently; `α_{b,i}` not typed; `ξ`, `r₂`, `δ`
retained from a formulation no longer used.

---

## 3. Code corrections — all applied (model v6)

Status: C1–C5 implemented in `route52_prototype.py` / `campaign_v5.py`,
verified by `test_v5.py` (all checks pass, peak `p^pre` now 23.00 kW in every
heated scenario), and the Route 52 campaign was restarted from an empty
result file. The superseded v5 outputs are in `archive_v5/`. C6 (table
generators) is outstanding and will be built against the v6 result files.


**C1 — preconditioning power exceeds the electric heater rating (binding).**
`p^pre` is bounded by charging acceptance (450 kW × derate) and by the charger
rating, but not by the 23 kW heater output that bounds in-service electric
heat. The precond window is four 0.25 h steps and delivered precond heat is
capped at 10 kWh, so up to 40 kW can be pushed through the heater in one step.

Measured, not assumed (`test_ppre_rating.py`, first stage fixed at the recorded
`policy_lam100` design):

| case | objective (CAD/yr) | peak `p^pre` | annual precond |
|---|---|---|---|
| A, as recorded | 2,372,750.1 | **40.0 kW** | 22,890 kWh |
| B, `p^pre ≤ 23 kW` | 2,373,018.7 | 23.0 kW | 21,801 kWh |

The bound is **active at the optimum** (peak sits exactly on the 40 kW
ceiling). Every recorded v5 incumbent is therefore infeasible for the
corrected model; the effect on cost is +269 CAD/yr on a fixed design, i.e.
below the 1 kCAD reporting tolerance but systematic. Protocol Section 5 forbids
reusing runs produced under the previous heating-power constraints, so the
campaign must be re-solved after the fix.

**C2 — preconditioning heat credit has no retention coefficient.**
Code credits `q^pre` to trip 1 at χ = 1, limited only by a 10 kWh cap.
Protocol 3.4 requires an explicit χ_{b,t} ∈ [0,1] decaying with the gap between
preconditioning and departure, plus a sensitivity. No data exists to estimate
χ (cabin temperature between pull-out and first trip is not telemetered), so a
documented conservative value is required. **Assumption decision needed.**

**C3 — one-plug-per-bus across sites is not enforced.**
`Σ_n u_{b,n,t} + u^pre_{b,t} ≤ 1` is satisfied structurally (dwell windows are
disjoint) and verified by `test_v5.py`, but is not a model constraint. Add it
so the property is structural rather than incidental.

**C4 — the FFH-free *procurement* case is missing from the campaign.**
The zero-cap run forces FFH-free *operation*; the manuscript distinguishes the
two. Add `x_κ = 0 ∀ κ: f(κ)=1`.

**C5 — records omit preconditioning quantities.** Add peak `p^pre`, annual
precond energy, and plug-hours to each run record so C1-type defects are
detectable from the archive.

**C6 — Tables IV and V have no generator.** Required by protocol Section 6.

---

## 3b. Open item found during the v6 run — loose economic baseline

`eps_1.00` (cap set at the baseline's own emissions, i.e. a relaxation of
nothing) returned `F1` = 2,371,676 against `econ_lam0`'s 2,372,208. The capped
run found a design 532 CAD/yr *cheaper* than the unconstrained baseline. This
is not a contradiction — it sits inside `econ_lam0`'s 982 CAD gap — but it
proves the baseline incumbent is suboptimal, and every increment measured
against it (notably the zero-emission premium) would be overstated by that
slack.

Handled in two places:
- `check_results_v5.py` check **22b** fails if any capped run beats the
  baseline, so this cannot pass silently into the manuscript.
- `campaign_v5.py` block **H2** re-solves `econ_lam0` warm-started from the
  best design found anywhere in the campaign.

The process now running (PID 2319) was launched before H2 was added, so for
this pass the re-solve must be triggered manually once the campaign ends.
Editing the running chain script was rejected as unsafe: `bash` reads a script
by byte offset while executing it.

## 4. Experiment classification

**Required rerun** (formulation changed by C1–C3): every Route 52 run in
`campaign_v5_results.json` — `econ_lam0`, `policy_lam100`, the seven `eps_*`
frontier points, and `lam_{200,500,1000,2000}`. 13 runs recorded, ~27 more
queued in the interrupted pass.

**New experiments**: out-of-sample residual reliability
(`reliability_v5.py`, written, never run); division-scale cases A–D and
near-optimal stability (`campaign_division_v5.py`, written, never run);
FFH-free procurement (C4); χ sensitivity (C2).

**Retained after verification**: none of the optimization results. The
empirical inputs (traction LORO fit, ECCC scenarios, GTFS blocks) and the
corrected figure *designs* are retained.

**Removed**: heat-pump sensitivity (v4 `campaign.py`), Scope 2 analysis, and
the Route 52-versus-division "coordination" comparison, which compares
different route systems and cannot identify coordination value.

---

## 5. Manuscript sections to remove or rewrite

- Remove: heat-pump experiment and its 48.7 kCAD/yr result (`main.tex` 771,
  999–1000, 1015, 1157); Scope 2 paragraph (1008–1010) and its mention in the
  Experimental Design (771). The heat-pump *citation* in the literature review
  (line 139, `hess2023`) stays — it is not the removed analysis.
- Rewrite: `eq:augmecon` + Alg. 1 (lexicographic); delete `eq:bigM`,
  `eq:cut-energy`, `eq:cut-deficit`; add heater-rating and χ equations; add a
  variable-domain block; define `Ω_ℓ`; state the 365-day horizon.
- Regenerate: all of Section VI (Results), the Abstract and the Conclusions,
  from v6 outputs only.
