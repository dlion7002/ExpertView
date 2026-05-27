# Deviation Report: Late Gauge Cadence on Line 2

Document ID: `deviation-report-line-2-gauge-cadence-2026-05-10`
Area: Process quality
Asset: `cnc-line-2-cnc-04`
Date opened: 2026-05-10
Status: containment closed, corrective action pending verification

## Deviation summary

During shift 2 on 2026-05-10, the post-maintenance inspection cadence was not followed after a fixture clamp sensor replacement on `cnc-line-2-cnc-04`. The first-good-part check passed, but the part-5 and part-10 checks were recorded together after part 14 had already run.

## Impact

No shipped nonconforming product was confirmed. Two parts were above the +0.030 mm reaction threshold but below the quality hold threshold. The late record reduced the team likelihood of catching a drift trend while it was still containable.

## Corrective action

- Add the restart cadence to the shift startup board for line 2.
- Require the shift lead to sign the part-5 and part-10 entries before the operator releases part 11.
- Retrain shift 3 operators on the difference between normal hourly inspection and controlled restart inspection.

## Verification plan

The next three maintenance restarts on line 2 must show on-time part-1, part-5, and part-10 bore gauge entries. Missing entries keep the corrective action open even if the measured parts are conforming.

## RCA note

This deviation is a process-control pattern, not proof of a mechanical or supplier cause. Use it to evaluate whether the control plan would have detected drift early enough during later incidents.
