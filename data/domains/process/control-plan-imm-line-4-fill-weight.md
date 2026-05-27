# Control Plan & SPC Excerpt: Line 4 Fill Weight and Seal Diameter

Document ID: `control-plan-imm-line-4-fill-weight`
Area: Process planning / SPC
Asset: `imm-line-4-press-04`
Part: HV-CAP-L4 on `mold-tool-mt-l4-09`
Revision: 2026-05-18

## Special characteristics and governing parameters

| Characteristic | Governing process parameter | Leading indicator | Reaction |
|---|---|---|---|
| Shot / fill weight | Hold (pack) pressure + barrel melt temperature | Weight trend vs nominal | If weight trends low after a changeover, verify the loaded recipe revision against the released revision before adjusting offsets. |
| Critical seal diameter | Pack pressure + cooling time | Diameter trend toward the low limit | Confirm the pack profile matches the released revision; do not re-center with offsets until verified. |
| Short-shot / sink rate (outer cavities) | Injection fill velocity + barrel temperature | Reject rate on cavities 6 and 8 | Check melt temperature and fill profile against the released recipe. |

## SPC interpretation guidance

Shot weight and seal diameter on this part are the leading indicators of a hold-pressure or melt-temperature setpoint shift. A simultaneous low-weight trend, low seal diameter, and rising short-shot or sink rate on the outer cavities is the signature of an under-packed, cool-running condition — the running parameters sitting below where the released recipe sets them — rather than tool wear or material variation, which tend to present as gradual single-characteristic drift.

## Changeover reaction rule

The first action when these characteristics move together immediately after a changeover is to compare the running recipe revision and active setpoints against the released revision on the setup sheet. Offset adjustments are not permitted until the loaded revision is confirmed to match the release.
