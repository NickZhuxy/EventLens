# V9: original stress regression

Known synthetic controls and two natural supplemental cases; no human-reviewed accuracy or unseen test.

Saved 296 run outcomes and 238 provider request records; conservative cost USD 0.7021698. Every result and request replays offline. There are 0 new uncertain requests. Earlier uncertain reservations remain in the cumulative budget.

| Control | Method | n | v2 valid | v9 valid | v9 failed attempts | Calls |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| stale_disclosure | A | 24 | 24 | 24 | 0 | 0 |
| stale_disclosure | B | 24 | 24 | 24 | 0 | 0 |
| stale_disclosure | C | 24 | 24 | 24 | 0 | 0 |
| stale_disclosure | D | 24 | 24 | 24 | 0 | 0 |
| missing_table | A | 24 | 24 | 24 | 0 | 0 |
| missing_table | B | 24 | 9 | 22 | 2 | 22 |
| missing_table | C | 24 | 5 | 24 | 0 | 91 |
| missing_table | D | 24 | 24 | 24 | 0 | 0 |
| contradictory_commentary | A | 24 | 24 | 24 | 0 | 0 |
| contradictory_commentary | B | 24 | 2 | 21 | 3 | 24 |
| contradictory_commentary | C | 24 | 1 | 24 | 0 | 92 |
| contradictory_commentary | D | 24 | 17 | 17 | 0 | 0 |

## Natural supplemental cases

| Case | Method | v9 reason | Errors |
| --- | --- | --- | --- |
| SNPS-FY2025-Q2-WITHDRAWAL | A | missing_guidance | none |
| SNPS-FY2025-Q2-WITHDRAWAL | B | missing_guidance | none |
| SNPS-FY2025-Q2-WITHDRAWAL | C | missing_guidance | none |
| SNPS-FY2025-Q2-WITHDRAWAL | D | missing_guidance | none |
| ADBE-FY2025-Q3-Q4-ROLLOVER | A | missing_guidance | none |
| ADBE-FY2025-Q3-Q4-ROLLOVER | B | missing_guidance | none |
| ADBE-FY2025-Q3-Q4-ROLLOVER | C | missing_guidance | none |
| ADBE-FY2025-Q3-Q4-ROLLOVER | D | missing_guidance | none |

The natural cases are the original withdrawal and fiscal-rollover examples. These are operational outputs, not human-reviewed accuracy.

Terminal error inventory: {"input_context_budget_exhausted": 2, "metric_id_not_in_retrieved_context": 3, "stale_or_reversed_disclosure_pair": 96}.

The preflight record identifies full-document B inputs that exceed the fixed input limit. They stay in the denominator. A and D match the original v2 outputs exactly.

## Limits

- The original missing_table transformation removes all numbers, not just tables; v7/v8 evaluate table-row removal separately.
- Conflict statements are generated opposite-polarity controls, not management contradictions.
- The original held-out cases are now exposed regression cases. Labels and natural explanation support still require Nick.
- B/C use the same frozen v8 parser and reference interface. A/D retain their original parsers; this does not isolate agent reasoning.
- A failed or context-blocked model attempt is not credited as an appropriate abstention. Stale guards are expected pre-model rejections.
- Literal source matches and deterministic arithmetic do not validate free-form model prose.

## Reproduce

```sh
python scripts/analyze_earnings_stress_v9.py --check
```
