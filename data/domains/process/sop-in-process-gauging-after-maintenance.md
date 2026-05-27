# SOP: In-Process Gauging After Maintenance

Document ID: `sop-in-process-gauging-after-maintenance`
Area: In-process quality
Applies to: line 2 CNC maintenance restarts
Revision: 2026-05-16

## Trigger

Use this SOP whenever a line 2 CNC asset restarts after maintenance affecting fixture clamp, hydraulic cylinder, spindle, cutting tools, gauging, or setup offsets.

## Required cadence

| Gate | Required action | Release condition |
|---|---|---|
| First-good-part | Measure and record bore diameter before any batch release. | Within tolerance and no unresolved setup note. |
| Part 5 | Measure before part 6 is released. | Trend remains below +0.030 mm from target. |
| Part 10 | Measure before part 11 is released. | Trend remains below +0.030 mm and shift lead signs log. |
| Part 20 | Measure if any prior entry is above +0.020 mm. | Process engineer reviews trend before normal cadence. |

## Drift reaction

If any restart measurement is above +0.030 mm from target, pause production and call the process engineer. If the part-10 check is missing, late, or entered after additional parts have run, treat the line as unreleased and contain parts since the prior conforming check.

## Records

Each entry must include:

- Part count.
- Bore diameter deviation.
- Gauge ID.
- Operator initials.
- Surface finish note.
- Any audible chatter, clamp-settle, or offset-change note.

Normal hourly inspection starts only after the restart sequence is complete.
