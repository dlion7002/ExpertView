# Process Capability Report: Bore Diameter May 2026

Document ID: `process-capability-bore-diameter-may-2026`
Area: Process engineering
Part family: hydraulic-valve sleeve, line 2
Report date: 2026-05-23

## Summary

The bore-diameter process for line 2 was capable during normal production in May 2026. Capability drops were clustered around maintenance restarts and late inspection records rather than a broad shift in the machining program.

## Capability snapshot

| Period | Asset | Sample size | Mean deviation | Cpk | Notes |
|---|---|---:|---:|---:|---|
| May 01-09 | `cnc-line-2-cnc-04` | 120 | +0.006 mm | 1.54 | Stable hourly checks. |
| May 10 restart | `cnc-line-2-cnc-04` | 24 | +0.021 mm | 0.93 | Late part-5 and part-10 restart checks. |
| May 11-20 | `cnc-line-2-cnc-04` | 180 | +0.008 mm | 1.48 | Stable after corrective review. |
| May 21-23 | `cnc-line-2-cnc-04` | 96 | +0.011 mm | 1.41 | No maintenance restart. |

## Engineering interpretation

The baseline program, nominal offsets, and standard inspection cadence are adequate when the line is not in controlled restart. The risk window is the first ten parts after service, when small clamp-settle or warm-up effects can become a trend before the hourly check would normally occur.

## Recommended controls

- Treat missing restart checks as process nonconformances even when the last measured part is inside tolerance.
- Review all offset changes made between part 1 and part 17 after any maintenance restart.
- Pair process capability review with mechanical evidence when chatter or surface banding appears during the same run.
