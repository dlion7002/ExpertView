# Recipe Change & Load Log: Line 4 Press-04 — 2026-05-26 Changeover

Document ID: `recipe-change-log-imm-line-4-changeover`
Area: Process control / recipe management
Asset: `imm-line-4-press-04`
Mold tool: `mold-tool-mt-l4-09`
Date: 2026-05-26

## Scope

This log records recipe selection and parameter-load events on the line 4 press-04 controller. It tracks which stored process recipe revision was loaded at each setup and what the controller reported as the active setpoints. It does not assign cause; it is a record of what was loaded and when.

## Released recipe baseline

The current released process recipe for part HV-CAP-L4 on mold tool `mold-tool-mt-l4-09` is **Rev F**, released 2026-05-18. Rev F superseded Rev D after a resin grade and colorant update earlier in May. Relative to Rev D, Rev F:

- Raised the hold (pack) pressure profile from 520 to 610 bar to hold part weight on the higher-melt-flow resin.
- Raised the barrel front-zone and nozzle temperature setpoints by 8 °C.
- Extended pack time by 0.4 s.

## Load events — 2026-05-26 changeover

| Time | Event | Recipe revision loaded | Source |
|---|---|---|---|
| 13:05 | Prior part run ended; tool change to `mold-tool-mt-l4-09` started. | — | Shift log |
| 13:52 | Operator selected a stored recipe for HV-CAP-L4 from the controller list and loaded it. | **Rev D** (2026-03-02) | Controller load event |
| 13:58 | Controller active setpoints after load: hold pressure 520 bar, barrel front 236 °C, pack time 2.1 s. | Rev D values | Controller readout |
| 14:20 | First parts measured; shot weight below nominal logged by quality. | — | Inspection log |

## Note

The laminated setup sheet at press-04 references the Rev F released parameters (610 bar hold, +8 °C front zone). The controller list still contained the superseded Rev D entry, and the loaded-revision tag on the running job reads `RevD-2026-03-02`. The discrepancy between the loaded revision and the released revision was flagged by the operator at 14:20 but was not yet reconciled at the time of this log.
