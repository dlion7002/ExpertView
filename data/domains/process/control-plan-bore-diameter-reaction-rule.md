# Control Plan Excerpt: Bore Diameter Reaction Rule

Document ID: `control-plan-bore-diameter-reaction-rule`
Area: Process quality
Part family: hydraulic-valve sleeve, line 2
Asset: `cnc-line-2-cnc-04`
Revision: 2026-05-18

## Controlled characteristic

| Characteristic | Nominal | Upper reaction threshold | Quality hold threshold | Gauge |
|---|---:|---:|---:|---|
| Finished bore diameter | 42.000 mm | +0.030 mm from target | +0.050 mm from target | digital bore gauge BG-L2-04 |

The bore diameter is a special characteristic for this part family. A shift can continue only while the in-process trend remains inside the reaction threshold.

## Required reaction

If one measured part exceeds +0.030 mm from target:

- Pause the next cycle at the station.
- Notify the shift lead and process engineer.
- Record tool offset, fixture clamp pressure, gauge ID, and part count.
- Measure the next two parts before releasing the cell.

If one measured part exceeds +0.050 mm from target:

- Stop production on `cnc-line-2-cnc-04`.
- Open a quality hold for all suspect parts since the last conforming check.
- Preserve the setup sheet and in-process inspection log.
- Do not restart until process engineering signs the reaction record.

## Post-maintenance note

After fixture, hydraulic clamp, spindle, or gauging maintenance, the first ten pieces require the post-maintenance inspection cadence in `sop-in-process-gauging-after-maintenance.md`. The normal hourly cadence does not apply until that restart sequence is complete.
