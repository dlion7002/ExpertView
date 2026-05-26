# FMEA Snippet: Spindle Bearing Wear and Preload Loss

Document ID: `mech-fmea-spindle-bearing-wear`
Area: Mechanical reliability
Asset family: CNC spindle assemblies, line 2
Revision: 2026-05-12

## Scope

This excerpt covers spindle bearing failure modes that can produce dimensional drift, surface finish defects, and audible chatter on line 2 CNC assets.

## Failure modes

| Failure mode | Local effect | System effect | Detection method | Severity | Occurrence | Detection |
|---|---|---|---|---:|---:|---:|
| Preload below service range | Radial runout increases under cutting load | Finished parts drift high on bore diameter | Runout check after warm-up | 8 | 4 | 3 |
| Over-preload after bearing service | Bearing temperature rises quickly | Chatter and surface tearing after warm-up | Thermal trend and sound check | 7 | 3 | 4 |
| Grease washout or insufficient film | Cage noise and intermittent chatter | Surface finish bands on finished parts | Vibration envelope trend | 7 | 3 | 5 |
| Lot-level bearing tolerance variation | Inconsistent preload response during installation | Repeat issue across assets using same batch | Receiving QA and batch trace | 8 | 2 | 6 |

## Notes from prior RCAs

- A mechanical finding should reference the installed bearing batch when chatter appears shortly after scheduled maintenance.
- Bearing batch variation does not prove supplier fault by itself; it is a trigger for supply-chain review when paired with runout or preload evidence.
- Hydraulic fixture bias and spindle bearing preload loss both show up as dimensional drift. The separation test is fixture repeatability unloaded versus spindle runout loaded after warm-up.

## Recommended evidence to collect

- Spindle runout at cold start and after a fifteen-minute warm-up.
- Bearing preload setting and torque wrench ID from the last service action.
- Installed bearing batch, supplier, receipt date, and any QA deviation notes.
- Operator description of chatter timing: immediately after clamp, only under cut, or after warm-up.
