# Purchasing System Query: Line 2 Bearing Lot Trace

Document ID: `purchasing-query-line-2-bearing-lots`
Area: Purchasing and crib traceability
Query run: 2026-05-25 08:10 local

## Query filters

| Filter | Value |
|---|---|
| Item family | Line 2 CNC spindle support bearing |
| Date range | 2026-05-01 through 2026-05-25 |
| Assets | `cnc-line-2-cnc-02`, `cnc-line-2-cnc-04` |
| Include staged inventory | Yes |

## Results

| Date | Asset | Work order | Batch | Supplier label | Status |
|---|---|---|---|---|---|
| 2026-05-03 | `cnc-line-2-cnc-02` | `WO-7594` | `A-119` | Regular bearing source | Closed |
| 2026-05-11 | `cnc-line-2-cnc-04` | `WO-7648` | `A-119` | Regular bearing source | Closed |
| 2026-05-19 | `cnc-line-2-cnc-02` | `WO-7698` | `B-227` | `Bearing Supplier - North` | Staged, not installed |
| 2026-05-24 | `cnc-line-2-cnc-04` | `WO-7716` | `B-227` | `Bearing Supplier - North` | Installed during shift-3 service |

## Trace note

`WO-7716` also references hydraulic-cylinder service on `hydraulic-cylinder-hc-l2-17`. The bearing batch and hydraulic service records should be reviewed together if the incident review needs asset-level traceability for `cnc-line-2-cnc-04`.
