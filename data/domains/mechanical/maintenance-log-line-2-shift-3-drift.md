# Maintenance Log: Line 2 Shift 3 Dimensional Drift

Document ID: `mech-maint-log-line-2-shift-3-drift`
Area: Line maintenance
Asset: `cnc-line-2-cnc-04`
Date: 2026-05-24
Shift: 3

## Event summary

At 22:40 -05:00, quality hold was opened after CNC line 2 asset `cnc-line-2-cnc-04` produced finished parts with bore diameter above the control limit. The issue appeared after hydraulic cylinder service on `hydraulic-cylinder-hc-l2-17` and after installation of spindle bearing batch `B-227` earlier in the week.

## Measurements

| Time | Part count | Bore diameter deviation | Surface finish | Operator note |
|---|---:|---:|---|---|
| 22:12 -05:00 | 1 | +0.018 mm | Normal | First-good-part check after maintenance. |
| 22:26 -05:00 | 8 | +0.031 mm | Normal | Fixture clamp sounded slightly uneven. |
| 22:40 -05:00 | 17 | +0.064 mm | Light banding | Chatter audible during roughing pass. |
| 22:51 -05:00 | 23 | +0.071 mm | Banding visible | Chatter stronger after spindle warm-up. |

## Checks performed

- Fixture return repeatability checked unloaded: within 0.012 mm after three cycles.
- Hydraulic pressure trace showed minor ripple at clamp settle but no sustained pressure decay.
- Tool wear check did not explain the bore drift.
- Warm spindle runout check was requested but not completed before the quality hold.

## Shift handoff note

The hydraulic cylinder service remains a possible contributor because the issue began after the repair. The stronger clue is that chatter increased after warm-up, which aligns with preload loss or bearing fit variation on `spindle-04`. Bearing batch `B-227` should be included in the next review.
