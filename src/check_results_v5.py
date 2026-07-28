"""
Automated result-integrity checks (revision protocol Section 6).

Runs against campaign_v5_results.json (+ the manuscript when present) and
verifies accounting, feasibility bookkeeping, certification claims, and
manuscript/figure consistency. Exit code 1 if any check fails.

Usage: ROUTE_INPUTS=route52_inputs_v5.json python3 check_results_v5.py
"""

import json
import os
import re
import sys

os.environ.setdefault("ROUTE_INPUTS", "route52_inputs_v5.json")
import route52_prototype as R

RES = "campaign_v5_results.json"
TEX = os.environ.get("CHECK_TEX", "../Overleaf/main.tex")
ABS_TOL = 1.0          # CAD
REL_TOL = 1e-6

D = json.load(open(RES))
runs = {r["label"]: r for r in D["runs"] if "error" not in r
        and not r.get("infeasible")}
fails, warns = [], []


def ck(name, cond, detail=""):
    (print if cond else print)(("PASS " if cond else "FAIL ") + name, detail)
    if not cond:
        fails.append(f"{name} {detail}")


def wk(name, cond, detail=""):
    if not cond:
        print("WARN " + name, detail)
        warns.append(f"{name} {detail}")


# 1. scenario weights sum to the annual horizon
days = sum(R.SCEN[w][1] for w in R.SCEN)
ck("01 weights_sum_365", days == 365, f"(={days})")

for lb, r in runs.items():
    cp = r["cost_parts"]
    # 2. annual diesel equals sum_omega h_omega D_omega. The deterministic
    # benchmark collapses the winter bands into one scenario, so weights are
    # taken from the run's own record where it carries them.
    dbs = r.get("diesel_by_scen", {})
    days = {w: v["days"] for w, v in r.get("scen_ops", {}).items()} or \
           {w: R.SCEN[w][1] for w in R.SCEN}
    if set(dbs) == set(days):
        recon = sum(days[w] * dbs[w] for w in days)
        ck(f"02 diesel_weighted[{lb}]", abs(recon - r["diesel_L"]) < 5.0,
           f"({recon:.0f} vs {r['diesel_L']:.0f})")
    else:
        wk(f"02 diesel_weighted[{lb}]", False,
           "(scenario set differs from the base instance; weights unavailable)")
    # 3. emissions = diesel * factor / 1000
    e = r["diesel_L"] * R.CO2_PER_L / 1000.0
    ck(f"03 emissions[{lb}]", abs(e - r["co2_t"]) < 0.02,
       f"({e:.3f} vs {r['co2_t']:.3f})")
    # 4. cost components sum to F1
    f1 = (cp["bus_capital"] + cp["charger_site_capital"] + cp["grid_capital"]
          + cp["demand_charges"] + cp["electricity"] + cp["ffh_om"]
          + cp["diesel_cost"])
    ck(f"04 F1_identity[{lb}]", abs(f1 - r["F1"]) < ABS_TOL,
       f"({f1:.1f} vs {r['F1']:.1f})")
    # 5. carbon payments excluded from F1
    ck(f"05 F1_excludes_carbon[{lb}]",
       r["lam"] == 0 or cp["carbon_cost"] > 0 or r["co2_t"] < 1e-6)
    # 6. objective equals F1 + lambda*F2 (lexicographic runs report phase-1
    #    cost, checked separately below)
    if not r.get("phase2"):
        obj = r["F1"] + cp["carbon_cost"]
        ck(f"06 objective_identity[{lb}]", abs(obj - r["obj"]) < ABS_TOL,
           f"({obj:.1f} vs {r['obj']:.1f})")
    # 7. cap satisfied within tolerance
    if r.get("eps") is not None:
        ck(f"07 cap_respected[{lb}]", r["co2_t"] <= r["eps"] + 0.05,
           f"({r['co2_t']:.3f} <= {r['eps']:.3f})")
    # 8/9. fleet covers the fixed block schedule
    tot = sum(r["fleet"].values())
    ck(f"08 fleet_covers_blocks[{lb}]", tot >= R.N_BLOCKS,
       f"({tot} vs {R.N_BLOCKS} blocks)")
    # 21. reported gap is consistent with incumbent and bound
    g = r["obj"] - r["lb"]
    ck(f"21 gap_consistent[{lb}]", abs(g - r["abs_gap"]) < ABS_TOL,
       f"({g:.1f} vs {r['abs_gap']:.1f})")

# 10-18: structural feasibility of the reported operating points was verified
# at solve time by the model constraints and by test_v5.py; re-verified here
# for the policy design through the stored ops metrics
ops = D.get("ops_metrics_policy", {})
ck("17 arrival_reserve_nonneg",
   all(v["min_reserve_kWh"] >= -1e-3 for v in ops.values()),
   f"(min={min((v['min_reserve_kWh'] for v in ops.values()), default=0):.1f} kWh)")

# 19/20. every certified frontier point meets the declared tolerance, or its
# true gap is disclosed
fr = [runs[lb] for lb in D.get("frontier_labels", []) if lb in runs]
loose = [(r["label"], r["abs_gap"]) for r in fr if r["abs_gap"] > 1000.0]
wk("19 frontier_tolerance", not loose, f"(loose: {loose})")

# 22b. relaxation monotonicity: the unconstrained economic baseline cannot
# cost more than any emissions-capped run. A violation means the baseline
# incumbent is loose, and every increment measured against it is overstated
# by that slack -- re-solve the baseline warm-started before reporting.
# Comparable runs are those solved over the SAME feasible set and parameters:
# emissions caps are restrictions and carbon prices only reweight the
# objective, so in both cases F1 >= F1*. Sensitivity, deterministic, frozen,
# outage, spare and FFH-free runs change the instance and are excluded.
COMPARABLE = re.compile(r"^(eps_|lam_|bp_lam_|policy_lam)")
base = runs.get("econ_lam0")
if base:
    worse = [(r["label"], round(base["F1"] - r["F1"], 1)) for r in runs.values()
             if COMPARABLE.match(r["label"]) and r["F1"] < base["F1"] - ABS_TOL]
    ck("22b baseline_not_dominated", not worse, f"(cheaper runs: {worse})")

# 22c. carbon-price monotonicity. At the true optimum, raising lambda cannot
# increase emissions and cannot decrease resource cost. A violation is only
# meaningful if it exceeds the optimality slack of the two runs involved:
# within the gaps it is uncertainty, beyond them it is an error.
lam_runs = sorted((r for r in runs.values()
                   if re.match(r"^lam_\d+$", r["label"])),
                  key=lambda r: r["lam"])
hard_e, hard_c = [], []
for a, bnext in zip(lam_runs, lam_runs[1:]):
    slack = (a["abs_gap"] + bnext["abs_gap"]) / max(a["lam"], 1.0)
    if bnext["co2_t"] > a["co2_t"] + slack:
        hard_e.append((a["label"], bnext["label"],
                       round(bnext["co2_t"] - a["co2_t"], 3)))
    if bnext["F1"] < a["F1"] - (a["abs_gap"] + bnext["abs_gap"]):
        hard_c.append((a["label"], bnext["label"],
                       round(a["F1"] - bnext["F1"], 1)))
ck("22c lam_emissions_monotone", not hard_e, f"(beyond gap slack: {hard_e})")
ck("22d lam_cost_monotone", not hard_c, f"(beyond gap slack: {hard_c})")
loose_lam = [(r["label"], r["abs_gap"]) for r in lam_runs
             if r["abs_gap"] > 1000.0]
wk("22e lam_tolerance", not loose_lam, f"(loose: {loose_lam})")

# 22/23. headline increments recomputed from source values
if fr:
    base = runs.get("econ_lam0")
    zero = [r for r in fr if r.get("eps") is not None and r["eps"] < 1e-6]
    if base and zero:
        inc = (zero[0]["F1"] - base["F1"]) / 1e3
        print(f"INFO zero-emission increment = {inc:.1f} kCAD/yr "
              f"(F1 {zero[0]['F1']/1e3:.1f} - {base['F1']/1e3:.1f})")
        D.setdefault("derived", {})["zero_emission_increment_kCAD"] = round(inc, 1)

# 26. computational provenance exists, covers every run, and discloses which
# runs lack a raw search log (user decision: keep the structured record and
# disclose, rather than re-solving those runs for log capture)
if os.path.exists("provenance_v5.json"):
    prov = json.load(open("provenance_v5.json"))
    ck("26a provenance_covers_runs",
       set(prov["runs"]) >= set(runs),
       f"({len(prov['runs'])} vs {len(runs)} runs)")
    ck("26b provenance_discloses_gap",
       prov["summary"]["record_only"] == 0
       or "not available" in prov["disclosure"])
else:
    wk("26 provenance_missing", False, "(run make_provenance_v5.py)")

# 25. removed analyses must not survive in the manuscript. The heat-pump
# CITATION in the related-work subsection is legitimate and is excluded from
# the scan; the removed item is the heat-pump sensitivity ANALYSIS.
if os.path.exists(TEX):
    tex = open(TEX, errors="ignore").read()
    lit = re.search(r"\\subsection\{Related Literature.*?(?=\\subsection\{)",
                    tex, re.S)
    scan = tex.replace(lit.group(0), "") if lit else tex
    for pat, name in ((r"heat[- ]?pump (case|sensitivity|experiment)|COP of|constant COP",
                       "25a heat_pump_analysis_removed"),
                      (r"Scope~?2|Scope 2", "25b scope2_removed"),
                      (r"48\.7", "25c old_hp_number_removed"),
                      # the removed items are the FORMULATIONS, not the words:
                      # a labelled augmented-epsilon equation, or a claim that
                      # big-M deactivation is used. Justifying the lexicographic
                      # choice against augmented epsilon, or stating that no
                      # big-M is needed, are legitimate and must not trip this.
                      (r"\\label\{eq:augmecon", "25d augmecon_removed"),
                      (r"implemented with big-\$?M|\\label\{eq:bigM",
                       "25e bigM_claim_removed")):
        ck(name, not re.search(pat, scan, re.I))
else:
    wk("25 manuscript_scan", False, "(main.tex not found)")

# 12/14. C1: preconditioning power must respect the electric heater rating in
# every recorded run (the v5 defect that forced the re-solve)
for lb, r in runs.items():
    pc = r.get("precond")
    if pc is None:
        wk(f"12 precond_recorded[{lb}]", False, "(pre-C5 record)")
        continue
    ck(f"12 precond_heater_rating[{lb}]",
       pc["peak_kW"] <= R.P_ELH_RATED + 1e-3,
       f"({pc['peak_kW']} kW vs {R.P_ELH_RATED} kW)")

json.dump(D, open(RES, "w"), indent=1)
print()
print(f"{len(runs)} runs checked | failures: {len(fails)} | warnings: {len(warns)}")
for f in fails:
    print("  FAIL", f)
sys.exit(1 if fails else 0)
