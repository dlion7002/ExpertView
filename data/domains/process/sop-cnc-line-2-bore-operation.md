# SOP: CNC Line 2 Bore Machining Operation

Document ID: `sop-cnc-line-2-bore-operation`
Area: Manufacturing process
Part family: hydraulic-valve sleeve
Asset: `cnc-line-2-cnc-04`
Revision: 2026-05-15

## Purpose

This SOP defines the standard process sequence for machining the finished bore on hydraulic-valve sleeves on line 2. It covers process controls only; mechanical service diagnostics remain in the maintenance procedure.

## Standard sequence

1. Verify the active setup sheet matches part family HV-SLEEVE-L2.
2. Confirm bore gauge BG-L2-04 is active and within calibration date.
3. Run the roughing pass with the approved tool group and saved offset set.
4. Run the finishing pass after coolant flow and fixture clamp pressure stabilize.
5. Measure the first completed part and record bore deviation, surface condition, operator initials, and part count.
6. Continue under the control-plan cadence only after the required restart checks are complete.

## Process parameters

| Parameter | Standard range | Reaction note |
|---|---:|---|
| Roughing feed override | 95-105% | Hold if chatter note repeats on two measured parts. |
| Finishing offset change | +/- 0.010 mm per adjustment | Process engineer approval required above two changes in restart status. |
| Clamp settle observation | No visible oscillation after close | Record in the inspection log after maintenance. |
| Bore gauge temperature soak | Minimum 10 minutes at station | Do not use a cold gauge for restart release. |

## Restart constraint

After hydraulic clamp, fixture, spindle, or gauge maintenance, the operation remains in controlled restart until the first-good-part, part-5, and part-10 checks are complete and documented. Operators may not substitute the normal hourly check for this sequence.
