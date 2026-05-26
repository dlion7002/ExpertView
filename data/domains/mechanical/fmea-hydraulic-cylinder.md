# FMEA Snippet: Line 2 Hydraulic Cylinder Position Control

Document ID: `mech-fmea-hydraulic-cylinder`
Area: Mechanical reliability
Asset family: CNC line 2 hydraulic positioning cylinders
Revision: 2026-05-10

## Scope

This excerpt covers hydraulic cylinders used for workholding and fixture-position assist on CNC line 2. It is intended for maintenance planning and RCA reference.

## Failure modes

| Failure mode | Local effect | System effect | Detection method | Severity | Occurrence | Detection |
|---|---|---|---|---:|---:|---:|
| Rod-end clevis misalignment after cylinder replacement | Side-load on cylinder rod | Fixture returns with a slight angular bias | Dial indicator sweep at clamp pad | 7 | 3 | 4 |
| Air trapped after bleed procedure | Short oscillation during clamp settle | Dimensional drift on first parts after maintenance | Pressure trace ripple, audible chatter | 6 | 4 | 5 |
| Seal drag after new seal kit | Slow retract and inconsistent clamp force | Variable part location under cutting load | Clamp pressure decay test | 6 | 3 | 5 |
| Incorrect rod-end locknut torque | Position drift over the shift | Repeatability loss on finished parts | Witness mark movement | 8 | 2 | 4 |

## Known contributing conditions

- Cylinder replacement or seal-kit service should be followed by a line-speed dry cycle and a ten-part capability check.
- Shift-3 restarts are higher risk because the first production parts are often released before the pressure trace has stabilized.
- Hydraulic cylinder oscillation can resemble spindle bearing chatter in operator notes, but the two usually separate during an unloaded spindle runout test.

## Recommended controls

- Record the cylinder serial number, rod-end locknut torque, bleed confirmation, and first-good-part measurement in the maintenance log.
- If out-of-tolerance parts appear within two hours of hydraulic service, inspect fixture return repeatability before replacing cutting tools.
- If fixture return is stable but chatter persists under load, inspect spindle bearing preload and recent bearing batch history.
