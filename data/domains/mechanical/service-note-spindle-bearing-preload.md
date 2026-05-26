# Service Note: Spindle Bearing Preload Verification

Document ID: `mech-service-note-spindle-bearing-preload`
Vendor style: Internal maintenance standard
Applies to: Line 2 CNC spindle assemblies
Revision: 2026-05-02

## Purpose

Spindle bearing preload controls runout under load. Incorrect preload or bearing dimensional variation can produce chatter, surface banding, and gradual dimensional drift as the spindle warms.

## Verification procedure

1. Confirm installed bearing batch and supplier against the maintenance traveler.
2. Warm spindle for fifteen minutes at standard idle speed.
3. Measure radial runout at the tool interface.
4. Record bearing housing temperature before and after warm-up.
5. Compare vibration envelope to the last accepted baseline.
6. If runout exceeds the baseline by more than 0.025 mm, place the asset on hold and inspect preload.

## Batch sensitivity note

Batch-to-batch bearing tolerance variation can change the preload response even when the same service procedure is followed. If two or more assets using the same batch show chatter or warm-runout growth, treat the batch trace as RCA evidence and request supply-chain review.

## Accepted ranges

| Check | Expected range |
|---|---|
| Warm radial runout increase | <= 0.025 mm over cold baseline |
| Housing temperature increase | <= 11 C over fifteen-minute warm-up |
| Vibration envelope change | <= 15 percent over baseline |

## Field note

Hydraulic fixture problems usually show during clamp repeatability checks. Bearing preload problems usually grow stronger under cut or after spindle warm-up.
