# V6 conflict-reference pilot

Four exposed synthetic development controls, both B/C; operational evidence only.

Completed 8 B/C runs, 16 requests, USD 0.0570054 conservative cost, zero uncertain requests. All v5/v6 requests and results replay exactly. Combined v3–v6 cost: USD 0.5947704.

| Version | Method | Cases | Valid two-citation flags | Numerical outputs | Errors | Calls |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| v5 | B | 4 | 0 | 0 | 4 | 4 |
| v5 | C | 4 | 0 | 0 | 4 | 23 |
| v6 | B | 4 | 4 | 4 | 0 | 4 |
| v6 | C | 4 | 4 | 4 | 0 | 12 |

## Every paired result

| Case | Method | v5 flag | v6 flag | v6 calls |
| --- | --- | --- | --- | ---: |
| [ADBE-FY2025-Q1-Q2~v3-contradictory_commentary](../earnings-v6-preflight-2026-10-15/runs/ADBE-FY2025-Q1-Q2~v3-contradictory_commentary_B.json) | B | False | True | 1 |
| [ADBE-FY2025-Q1-Q2~v3-contradictory_commentary](../earnings-v6-preflight-2026-10-15/runs/ADBE-FY2025-Q1-Q2~v3-contradictory_commentary_C.json) | C | False | True | 2 |
| [BOX-FY2025-Q1-Q2~v3-contradictory_commentary](../earnings-v6-preflight-2026-10-15/runs/BOX-FY2025-Q1-Q2~v3-contradictory_commentary_B.json) | B | False | True | 1 |
| [BOX-FY2025-Q1-Q2~v3-contradictory_commentary](../earnings-v6-preflight-2026-10-15/runs/BOX-FY2025-Q1-Q2~v3-contradictory_commentary_C.json) | C | False | True | 3 |
| [INTU-FY2025-Q1-Q2~v3-contradictory_commentary](../earnings-v6-preflight-2026-10-15/runs/INTU-FY2025-Q1-Q2~v3-contradictory_commentary_B.json) | B | False | True | 1 |
| [INTU-FY2025-Q1-Q2~v3-contradictory_commentary](../earnings-v6-preflight-2026-10-15/runs/INTU-FY2025-Q1-Q2~v3-contradictory_commentary_C.json) | C | False | True | 3 |
| [SNPS-FY2025-Q1-Q2~v3-contradictory_commentary](../earnings-v6-preflight-2026-10-15/runs/SNPS-FY2025-Q1-Q2~v3-contradictory_commentary_B.json) | B | False | True | 1 |
| [SNPS-FY2025-Q1-Q2~v3-contradictory_commentary](../earnings-v6-preflight-2026-10-15/runs/SNPS-FY2025-Q1-Q2~v3-contradictory_commentary_C.json) | C | False | True | 4 |

## Interpretation

The explicit ID fields and per-request reference choices remove the observed quote/ID mismatch on this pilot. Both B and C succeed; the result does not show that the agent loop outperforms the single-pass method. Every earlier failure remains saved.

## Limits

- Both methods share the deterministic candidate parser; no agent superiority claim.
- The statements are synthetic, not management contradictions.
- One run per exposed case does not establish natural-conflict accuracy or generalization.
- References and numerical outputs are validated; free-form model prose is unvalidated.
- All natural labels and semantic judgments await Nick. Costs are conservative token estimates, not invoices.

## Reproduce

```sh
python scripts/analyze_earnings_protocol_v6.py --check
```
