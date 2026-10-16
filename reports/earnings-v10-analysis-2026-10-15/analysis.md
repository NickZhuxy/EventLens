# V10: explicit annual guidance withdrawal

Four live outcomes on two exposed natural supplemental cases; no human-reviewed accuracy.

Completed 4 outcomes and 8 provider requests for USD 0.0232560; 0 uncertain requests. All requests and results replay offline.

| Case | Method | v9 reason | v10 reason | Errors | Calls |
| --- | --- | --- | --- | --- | ---: |
| SNPS-FY2025-Q2-WITHDRAWAL | B | missing_guidance | guidance_withdrawn | none | 1 |
| SNPS-FY2025-Q2-WITHDRAWAL | C | missing_guidance | guidance_withdrawn | none | 3 |
| ADBE-FY2025-Q3-Q4-ROLLOVER | B | missing_guidance | missing_guidance | none | 1 |
| ADBE-FY2025-Q3-Q4-ROLLOVER | C | missing_guidance | missing_guidance | none | 3 |

The new code also replays 290 non-withdrawal B/C recordings from v8/v9 with identical requests, traces, evidence and outcomes. This is controller regression using saved responses, not new model inference.

## Limits

- The withdrawal rule is narrow: an explicit suspension/withdrawal of financial guidance for the full fiscal year, optionally alongside its quarter.
- The unique prior revenue target supplies currency, basis, definition and units. The source proves withdrawal, not a replacement value.
- Negated, conditional, partial-metric, quarterly-only and unsupported wording abstain. Natural semantic review remains pending.
- Recorded regression reuses prior model responses; it is not fresh inference on the full corpus.
- The rollover case remains an abstention; the system does not compare different fiscal-year targets.

## Reproduce

```sh
python scripts/analyze_earnings_withdrawal_v10.py --check
```
