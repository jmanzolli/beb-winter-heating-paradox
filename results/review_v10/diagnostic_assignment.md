## 5. Check on the design-day result (local diagnostic, 25 draws per band)

The design-day design passes 98% of extreme days but only 39% of very cold days
(`trac`), which is not monotone in temperature. Cause: the harness fixes the
day-ahead block-to-bus assignment from the planning solve at the band
representative temperature. That solve is cost-indifferent between assignments,
so the three heater buses and two extended-range buses land on arbitrary blocks
with zero margin.

| Band | Planned (fixed) assignment | Assignment re-optimised on the realised day |
|---|---|---|
| very cold | 12 of 25 days pass, mean shortfall 26.4 kWh | 25 of 25 pass |
| extreme | 25 of 25 | 25 of 25 |

Planned heater-bus blocks: cold [0, 3, 10], very cold [0, 6, 10], extreme
[7, 14, 15], severe [1, 14, 16].

Consequences:
- Homogeneous fleets (D0: 18 heater buses; 25 kWh reserve: 18 standard buses)
  are unaffected: any assignment is the same.
- Mixed fleets (design-day; 100 kWh reserve: 16 standard + 2 extended) are
  penalised by an arbitrary tie-break. Their reserve-compliance numbers are a
  lower bound for a planner who places the scarce buses well.
- D4 (17 standard + 1 extended) was checked on the severe band (`trac`, 16
  draws): 8 of 16 days pass with the planned assignment and 8 of 16 with the
  re-optimised one; mean shortfall 112.2 against 110.5 kWh. D4 is in practice
  unaffected. The 100 kWh reserve design has not been checked.
- 12.8 of the 15.2 design-day breach days per winter (`trac`) come from the
  very cold band, i.e. mostly from this artefact.
- Decision (2026-11-10): hedged day-ahead assignment. Per band, the harness
  takes the assignment that tolerates the largest uniform rise in traction
  energy on a cold day of the band (10th percentile of its daily means);
  `reliability_v10.py`, `hedged_assignment`, run by `run_hedged_v10.sh` for the
  design-day and 100 kWh reserve designs. Results: `rel_v10h_*.json`.
- Local check of the hedged assignment for the design-day design (same 25
  draws): very cold 25 of 25 pass, cold 25 of 25. Tolerated multiplier: mild
  1.57, cold 1.46, very cold 1.34, extreme 1.14, severe 0.99. Heater and
  extended-range buses sit on blocks 7, 14, 15, 16, 17 in every band.

- Outcome of the re-run (1,000 draws per band, finished 2026-11-11 01:38 WET,
  about 3 h): design-day breach days per winter fall from 15.2 / 21.6 / 24.8
  (`trac` / `data` / `cv0.20`) to 1.16 / 2.36 / 4.12. The gain is in the cold
  and very cold bands. The severe band is unchanged (54.6 / 37.0 / 19.9% of
  days reserve-compliant under both assignments), and the extreme band is
  slightly lower with the hedged assignment (97.3 against 98.1%, 86.9 against
  89.7%, 70.5 against 73.4%): a plan hedged against uniform stress is not the
  best plan for every draw. The 100 kWh reserve design moves little (0.21 /
  0.28 / 0.40 against 0.21 / 0.30 / 0.49 breach days per winter).
- Numbers to use: hedged assignment for the two mixed-fleet designs
  (`rel_v10h_*`), first-run numbers for D0, D4 and the 25 kWh reserve design
  (`rel_v10_*`).

Diagnostics: scratch scripts, not part of the bundle.
