"""Cross-check every quantitative claim in the manuscript and supplement
against the v8 archives.

check_results_v5.py verifies model-internal invariants (monotonicity,
tolerances, domination). This is the complementary direction: it takes the
numbers that appear in the prose and confirms each one is what the archive
actually says. Prose is where stale values survive, because nothing recomputes
it -- the tables and figures are generated, the sentences around them are not.

Run: ROUTE_INPUTS=route52_inputs_v7.json python3 audit_v8.py
"""
import json
import os
import re
import sys

RES = os.environ.get("AUDIT_RES", "campaign_v8_results.json")
DIV = os.environ.get("AUDIT_DIV", "campaign_division_v8.json")
DETB = os.environ.get("AUDIT_DETBAND", "detband_v8.json")
RELB = os.environ.get("AUDIT_REL_BASE", "rel_v8_econ_full.json")
RELZ = os.environ.get("AUDIT_REL_ZERO", "rel_v8_zero_cv00.json")
CALIB = os.environ.get("AUDIT_CALIB", "calib_chargers.json")
MAIN = os.environ.get("AUDIT_MAIN", "../Overleaf/main.tex")
SUPP = os.environ.get("AUDIT_SUPP", "../Overleaf/supplementary.tex")

R = {r["label"]: r for r in json.load(open(RES))["runs"]
     if "error" not in r and not r.get("infeasible")}
RAW = json.load(open(RES))
DV = json.load(open(DIV))["cases"]
DB = json.load(open(DETB))
RB = json.load(open(RELB))["levels"]
RZ = json.load(open(RELZ))["levels"]
CB = json.load(open(CALIB)) if os.path.exists(CALIB) else None

W = {"mild": 45, "cold": 45, "verycold": 36, "extreme": 19, "severe": 6}
WT = sum(W.values())


def band(levels, cv, key):
    lv = levels[f"heat_cv_{cv:.2f}"]
    return 100 * sum(lv[w][key] * W[w] for w in W) / WT


main = open(MAIN).read()
supp = open(SUPP).read()
main = "\n".join(l for l in main.split("\n") if not l.strip().startswith("%"))
supp = "\n".join(l for l in supp.split("\n") if not l.strip().startswith("%"))
# Collapse whitespace. Patterns must survive re-wrapping: anchoring them on
# line breaks made the audit fail whenever a paragraph was retrimmed, which is
# exactly when it most needs to work.
main = re.sub(r"\s+", " ", main)
supp = re.sub(r"\s+", " ", supp)

fails, checks = [], 0


def claim(where, text, expected, fmt="{:.1f}", tol=None):
    """Assert that `text` appears in `where`, and that it encodes `expected`."""
    global checks
    checks += 1
    doc = main if where == "main" else supp
    if text in doc:
        return
    fails.append(f"[{where}] MISSING/STALE: {text!r} "
                 f"(archive says {fmt.format(expected)})")


def num_in(where, pattern, expected, tol, label):
    """Find `pattern` (one capture group) and compare the captured number."""
    global checks
    checks += 1
    doc = main if where == "main" else supp
    m = re.search(pattern, doc)
    if not m:
        fails.append(f"[{where}] {label}: pattern not found ({pattern!r})")
        return
    got = float(m.group(1).replace(",", "").replace("{", "").replace("}", ""))
    if abs(got - expected) > tol:
        fails.append(f"[{where}] {label}: text says {got:g}, "
                     f"archive says {expected:g}")


b = R["econ_lam0"]
z = R["eps_0.00"]
det = R["det_meanT"]

# ---------------------------------------------------------------- RQ1
num_in("main", r"burns ([\d,]+)~L of diesel per year", b["diesel_L"], 1, "baseline diesel")
num_in("main", r"at ([\d,]+\.\d)~kCAD/yr, certified", b["F1"] / 1e3, 0.05, "baseline F1")
num_in("main", r"certified to within (\d+\.\d+)~kCAD", b["abs_gap"] / 1e3, 0.005, "baseline gap")
num_in("main", r"onboard emissions are ([\d.]+)~t", b["co2_t"], 0.05, "baseline CO2")
num_in("main", r"That is (\d+)\\% below the ([\d,]+)~L that Route~52",
       round(100 * (10305 - b["diesel_L"]) / 10305), 1, "diesel gap pct")

# per-band FFH share and severe diesel
so = b["scen_ops"]
sev = so["severe"]
share_sev = 100 * sev["q_ffh_kWh"] / (sev["q_el_kWh"] + sev["q_ffh_kWh"])
num_in("main", r"and (\d+)\\% on severe days", share_sev, 1, "severe FFH share")
num_in("main", r"severe days at (\d+)~L/day", sev["diesel_L"], 1, "severe diesel/day")
for nm, w in (("very-cold", "verycold"), ("extreme", "extreme")):
    s = so[w]
    sh = 100 * s["q_ffh_kWh"] / (s["q_el_kWh"] + s["q_ffh_kWh"])
    num_in("main", rf"(\d+)\\% of delivered heat in the {nm} band" if w == "verycold"
           else rf"(\d+)\\% in the {nm} band", sh, 1, f"{w} FFH share")

# ---------------------------------------------------------------- calibration
if CB:
    best = CB["closest"]
    num_in("main", r"reproduce the observed fuel use within ([\d.]+)\\%",
           abs(100 * (best["diesel_L"] - 10305) / 10305), 0.2, "calib pct")
    num_in("main", r"within [\d.]+\\% \(([\d,]+)~L\)", best["diesel_L"], 1, "calib diesel")
    c300 = next(c for c in CB["cases"] if c["n"] == 3 and c["kW"] == 300)
    num_in("main", r"optimum selects burn ([\d,]+)~L", c300["diesel_L"], 1, "calib 3x300")


# ------------------------------------------------------ RQ3: uncertainty
num_in("main", r"keeping only three burners at ([\d.]+)~kCAD/yr less",
       (b["F1"] - det["F1"]) / 1e3, 0.05, "det saving")
num_in("main", r"short by ([\d,]+)~kWh on a typical extreme",
       DB["det_meanT"]["extreme"]["shortfall_kWh"], 1, "detband extreme")
num_in("main", r"and ([\d,]+)~kWh on a severe one",
       DB["det_meanT"]["severe"]["shortfall_kWh"], 1, "detband severe")

EV = json.load(open(os.environ.get("AUDIT_EVPI", "evpi_vss.json"))) \
    if os.path.exists("evpi_vss.json") else None
if EV:
    num_in("main", r"saves ([\d.]+)~kCAD/yr in resources",
           EV["resource_saving_of_EEV_CAD_yr"] / 1e3, 0.05, "EEV resource saving")
    num_in("main", r"leaves ([\d,]+)~kWh of cabin heat",
           EV["EEV_unmet_heat_kWh_yr"], 1, "EEV unmet heat")
    num_in("main", r"valued above ([\d.]+)~CAD/kWh",
           EV["breakeven_comfort_price_CAD_per_kWh"], 0.01, "comfort break-even")

num_in("main", r"both near ([\d.]+)\\% of winter days",
       band(RB, 0.0, "p_soc_floor_ok"), 0.05, "floor, both designs")
num_in("main", r"([\d.]+)\\% against 90\.3\\% overall",
       band(RB, 0.0, "p_all_trips_served"), 0.05, "baseline reserve")
num_in("main", r"99\.6\\% against ([\d.]+)\\% overall",
       band(RZ, 0.0, "p_all_trips_served"), 0.05, "zero reserve")
num_in("main", r"of 0\.40 the baseline holds the\s*floor on ([\d.]+)\\%",
       band(RB, 0.40, "p_soc_floor_ok"), 0.05, "cv40 floor")

RM = os.environ.get("AUDIT_RELMATCH", "relmatch_v8.json")
if os.path.exists(RM):
    MM = {r["label"]: r for r in json.load(open(RM))["runs"]}
    gammas = sorted(int(l.split("_r")[1]) for l in MM if l.startswith("relmatch_eps0_r"))
    top = f"relmatch_eps0_r{gammas[-1]}"
    prem_top = (MM[top]["F1"] - b["F1"]) / 1e3
    num_in("main", r"raises its cost to \$\+\$([\d.]+)~kCAD/yr", prem_top, 0.1, "relmatch top cost")
    num_in("main", r"by\s*at least (\d+)~kCAD/yr",
           prem_top - (z["F1"] - b["F1"]) / 1e3, 1.0, "relmatch delta")

# ------------------------------------------------------ RQ2: frontier
num_in("main", r"extended batteries, for \+([\d.]+)~kCAD/yr",
       (R["eps_0.70"]["F1"] - b["F1"]) / 1e3, 0.1, "D1 increment")
num_in("main", r"Lawrence Station, for \+([\d.]+)~kCAD/yr",
       (R["eps_0.35"]["F1"] - b["F1"]) / 1e3, 0.1, "D2 increment")
num_in("main", r"terminal chargers, at \+([\d.]+)~kCAD/yr",
       (z["F1"] - b["F1"]) / 1e3, 0.1, "D4 increment")
num_in("main", r"about ([\d.]+)\\% of annual fleet cost",
       100 * (z["F1"] - b["F1"]) / b["F1"], 0.1, "premium as pct")
bp = RAW["breakpoint_prices"]
num_in("main", r"price lies between ([\d,{}]+) and", bp[0], 1, "breakpoint low")
num_in("main", r"and ([\d,{}]+)~CAD/t\\COtwo\{\}, an order", bp[1], 1, "breakpoint high")

# ------------------------------------------------------ RQ4: coordination
A = DV["A_fragmented"]
lbA = sum(v["lb_solver"] for v in A["per_route"].values())
best_coord = min(v["differentiating_cost"] for k, v in DV.items()
                 if k != "A_fragmented" and v.get("differentiating_cost"))
bestk = min((k for k in DV if k != "A_fragmented" and DV[k].get("differentiating_cost")),
            key=lambda k: DV[k]["differentiating_cost"])
num_in("main", r"together is worth at least ([\d.]+)~kCAD/yr", (lbA - best_coord) / 1e3, 0.1, "coord saving")
num_in("main", r"per-route lower bounds \(([\d,{}]+\.\d)~kCAD\)", lbA / 1e3, 0.1, "A bound")
num_in("main", r"solution found costs ([\d,{}]+\.\d)~kCAD", best_coord / 1e3, 0.1, "coord incumbent")
num_in("main", r"fleet from (\d+) of 183", A["n_ffh"], 0, "fragmented FFH")
num_in("main", r"from \d+ of 183 to (\d+)", DV[bestk]["n_ffh"], 0, "coordinated FFH")
num_in("main", r"reaches ([\d.]+)~MW against",
       sum(v["peak_depot_kW"] for v in A["per_route"].values()) / 1e3, 0.05, "fragmented peak")
num_in("main", r"against ([\d.]+)~MW when the division", DV[bestk]["peak_depot_kW"] / 1e3, 0.05, "coordinated peak")

# ---------------------------------------------------------------- supplement
A_ = DV["A_fragmented"]
lbA_ = sum(v["lb_solver"] for v in A_["per_route"].values())
bc_ = min(v["differentiating_cost"] for k, v in DV.items()
          if k != "A_fragmented" and v.get("differentiating_cost"))
num_in("supp", r"certified ([\d.]+)~kCAD/yr minimum", (lbA_ - bc_) / 1e3, 0.1, "supp saving")
num_in("supp", r"underbrace\{([\d,{}]+\.\d)\}_\{\\text\{sum of A", lbA_ / 1e3, 0.1, "supp A bound")
num_in("supp", r"underbrace\{([\d,{}]+\.\d)\}_\{\\text\{best coordinated", bc_ / 1e3, 0.1, "supp coord incumbent")
num_in("supp", r"\\;=\\; ([\d.]+)~\\text\{kCAD/yr\}", (lbA_ - bc_) / 1e3, 0.1, "supp saving eq")

bp_ = RAW["breakpoint_prices"]
num_in("supp", r"frontier are ([\d,{}]+),", bp_[0], 1, "supp bp0")
num_in("supp", r"frontier are [\d,{}]+, ([\d,{}]+),", bp_[1], 1, "supp bp1")
num_in("supp", r"frontier are [\d,{}]+, [\d,{}]+, ([\d,{}]+)", bp_[2], 1, "supp bp2")
num_in("supp", r"retained at ([\d.]+)~t/yr", R["bp_lam_1032"]["co2_t"], 0.05, "supp bp0 co2")
num_in("supp", r"is selected at ([\d.]+)~t/yr", R["bp_lam_1974"]["co2_t"], 0.05, "supp bp1 co2")

num_in("supp", r"extended batteries enter at ([\d.]+)~t", R["eps_0.70"]["co2_t"], 0.05, "supp ext entry")
num_in("supp", r"opportunity charging at ([\d.]+)~t", R["eps_0.35"]["co2_t"], 0.05, "supp opp entry")

prov = json.load(open(os.environ.get("AUDIT_PROV", "provenance_v8.json")))
num_in("supp", r"archived for all (\d+) runs", prov["summary"]["n_runs"], 0, "supp log count")
num_in("supp", r"with (\d+) threads", int(str(prov["solver"]["threads"]).split("/")[0]), 0, "supp threads")

st = [DV[k] for k in DV if k != "A_fragmented" and DV[k].get("differentiating_cost")]
if len(st) >= 2:
    lo = min(v["n_ffh"] for v in st); hi = max(v["n_ffh"] for v in st)
    spread = (max(v["differentiating_cost"] for v in st)
              - min(v["differentiating_cost"] for v in st)) / 1e3
    num_in("supp", r"They span (\d+) to \d+ FFH-equipped", lo, 0, "supp stability lo")
    num_in("supp", r"They span \d+ to (\d+) FFH-equipped", hi, 0, "supp stability hi")
    num_in("supp", r"within ([\d.]+)~kCAD/yr of one another", spread, 0.2, "supp stability spread")

# ------------------------------------------------- reliability-matched premium
RM = os.environ.get("AUDIT_RELMATCH", "relmatch_v8.json")
if os.path.exists(RM):
    MM = {r["label"]: r for r in json.load(open(RM))["runs"]}
    gammas = sorted(int(l.split("_r")[1]) for l in MM if l.startswith("relmatch_eps0_r"))
    top = f"relmatch_eps0_r{gammas[-1]}"
    prem_top = (MM[top]["F1"] - b["F1"]) / 1e3
    num_in("main", r"raises its cost to \$\+\$([\d.]+)~kCAD/yr", prem_top, 0.1, "relmatch top cost")
    fn = f"rel_v8_{top}.json"
    if os.path.exists(fn):
        LV = json.load(open(fn))["levels"]["heat_cv_0.00"]
        rs = 100 * sum(LV[w]["p_all_trips_served"] * W[w] for w in W) / WT
        base_rs = band(RB, 0.0, "p_all_trips_served")
        num_in("main", r"by at least (\d+)~kCAD/yr",
               prem_top - (z["F1"] - b["F1"]) / 1e3, 1.0, "relmatch delta")

# supplement robustness prose: these were wrong once and nothing else checks them
_pol = R.get("policy_lam100")
if _pol:
    for lab, pat in (("derate_mild", r"emissions fall about (\d+)\\% under the milder"),
                     ("derate_harsh", r"rise about (\d+)\\% under the harsher")):
        if lab in R:
            pct = abs(100 * (R[lab]["co2_t"] - _pol["co2_t"]) / _pol["co2_t"])
            num_in("supp", pat, pct, 1.0, f"supp {lab} pct")

# marginal abatement structure: the uniform-cost claim was wrong once
_bp = RAW["breakpoint_prices"]
num_in("main", r"starts at about ([\d.]+)~kCAD per tonne", _bp[0] / 1e3, 0.1, "marginal start")
num_in("main", r"reaches ([\d.]+)~kCAD for", _bp[-1] / 1e3, 0.1, "marginal end")
num_in("main", r"averaging ([\d.]+)~kCAD per tonne over full",
       (z["F1"] - b["F1"]) / 1e3 / b["co2_t"], 0.1, "average abatement")

# severe-band sweep: verified against the pulled v8 variant archives
import glob as _glob
for _f, _tag in (("sev115_v8.json", "1.15"), ("sev130_v8.json", "1.30")):
    if os.path.exists(_f):
        _r = {x["label"]: x for x in json.load(open(_f))["runs"]}["econ_lam0"]
        checks += 1
        same = (_r["fleet"] == b["fleet"] and _r["chargers"] == b["chargers"])
        if not same:
            fails.append(f"[supp] sev sweep {_tag}: design differs from baseline "
                         f"but prose claims identical")

print(f"audit: {checks} checks")





if fails:
    print(f"\n{len(fails)} MISMATCH(ES):")
    for f in fails:
        print("  " + f)
    sys.exit(1)
print("all prose claims match the v8 archives")
