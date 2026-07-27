# Data sources for Route 52 prototype v3

Generated inputs live in `route52_inputs.json` (rebuild with `python3 fit_inputs.py`).

| Input | Source | Status |
|---|---|---|
| Traction interface `e_km(T,v) = 0.661 + 0.0074·max(0, 5−T) + 0.0016·v` | Fitted on 13,757 runs, TTC telemetry (`heating_system_study/data/TTC_Preprocessed_version2_2.xlsx`), drivetrain energy only (heating excluded — matches model split). R² = 0.117 (trip-level noise; same order as Paper 1 trip-level fits) | Fitted; swap in Choga's model when interface confirmed |
| Route 52 blocks | GTFS-derived `route_summary.xlsx` (same repo): 52A Lawrence Stn↔Pearson (19.3/20.2 km, 128-min cycle, 7 buses), 52D Lawrence Stn↔Victory-McNaughton (21.9/22.0 km, 140-min, 7 buses), 52G Lawrence West↔Martin Grove (11.2/11.9 km, 86-min, 4 buses); 18 blocks total; layovers/headways from schedule | Real |
| Heating demand | Paper 1 Bayesian posterior medians (Table 4, New Flyer), per-branch stop rates from route summary | Real (route-level pax rate 60/h still TODO) |
| Scenario day counts | ECCC climate-daily API, Toronto City (climate ID 6158355), winters 2024-25 + 2025-26, mean daily temp bands, 2-winter average: mild(+2.5°)45 d, cold(−2.5°)45, verycold(−7.5°)36, extreme(−12.5°)19, severe(−17.5°)6 — 151 winter days | Real (2 winters; extend to 10 for the paper) |
| Grid upgrade tiers | 200 $/kW (NREL/industry depot-upgrade range 100–300 $/kW). Toronto Hydro publishes no schedule — capital contribution is project-specific NPV shortfall (Conditions of Service). Sensitivity 100–300 | Benchmark assumption |
| FFH annual O&M | 1,000 $/yr per retained heater (annual burner service assumption). CALSTART FFH white paper (2021) documents fuel use (~30 gal/bus/winter-month) but no O&M cost; no public transit number found. Sweep 500–2,000 | Assumption (documented) |
| Costs/tariffs | Paper 1 Appendix C (bus $1M, battery 150 $/kWh, charger cost curve, diesel 1.86 CAD/L); Ontario winter TOU; demand charge 12 $/kW-month × 5 winter months | Real |

Sources: [Toronto Hydro Conditions of Service](https://www.torontohydro.com/documents/d/guest/conditions-of-service-main-document-nov-2024-draft) · [NREL financial analysis of BE transit buses](https://afdc.energy.gov/files/u/publication/financial_analysis_be_transit_buses.pdf) · [CALSTART FFH white paper](https://calstart.org/wp-content/uploads/2022/01/FFH-White-Paper_Final.pdf) · [ECCC climate-daily API](https://api.weather.gc.ca/collections/climate-daily)

Note on "Choga's study": no folder named Choga found; assumed = `heating_system_study` repo (`src/energy_allocation_model.py`, adapts Manzolli et al. 2025 with traction + heating submodel). Traction interface fitted directly from that repo's telemetry as stand-in. **Confirm with Choga.**
