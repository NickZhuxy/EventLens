# V4 retrieval-batching pilot

Eight exposed development cases. Operational results, not reviewed accuracy or unseen validation.

Completed **8 C runs** and **43 model requests** at **USD 0.1034148** conservative token cost, under the approved USD 3 cap. Combined v3/v4 cost: **USD 0.3410172**, within the prior USD 6 allocation. All v4 requests and results replay exactly with zero network calls.

## Matched development results

| Version / method | Case type | n | Completed without errors | Numerical outputs | Valid two-citation flags | Terminal errors | Calls |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| v3 B (existing) | contradictory_commentary | 4 | 2 | 2 | 1 | 2 | 4 |
| v3 B (existing) | real | 4 | 2 | 2 | unreviewed | 2 | 4 |
| v3 C | contradictory_commentary | 4 | 3 | 2 | 0 | 1 | 32 |
| v3 C | real | 4 | 3 | 2 | unreviewed | 1 | 25 |
| v4 C | contradictory_commentary | 4 | 3 | 2 | 1 | 1 | 24 |
| v4 C | real | 4 | 3 | 3 | unreviewed | 1 | 19 |

Numerical output coverage is not accuracy. A completed real-case abstention can still be wrong. Terminal failures are never counted as valid conflict flags.

## Paired outcomes

| Case | v3 C numeric | v4 C numeric | v3 C errors | v4 C errors | v3 C calls | v4 C calls |
| --- | --- | --- | --- | --- | ---: | ---: |
| ADBE-FY2025-Q1-Q2 | True | True | False | False | 7 | 6 |
| ADBE-FY2025-Q1-Q2~v3-contradictory_commentary | True | True | False | False | 8 | 5 |
| BOX-FY2025-Q1-Q2 | False | True | False | False | 7 | 3 |
| BOX-FY2025-Q1-Q2~v3-contradictory_commentary | True | True | False | False | 8 | 6 |
| INTU-FY2025-Q1-Q2 | True | True | False | False | 4 | 4 |
| INTU-FY2025-Q1-Q2~v3-contradictory_commentary | False | False | False | False | 8 | 7 |
| SNPS-FY2025-Q1-Q2 | False | False | True | True | 7 | 6 |
| SNPS-FY2025-Q1-Q2~v3-contradictory_commentary | False | False | True | True | 8 | 6 |

## Retrieval and conflict diagnosis

The controller accepted **22/27** multiple-function responses. Exact batch actions and any rejection reasons are retained in `analysis.json`.

| Synthetic control | v3 retrieved both | v4 retrieved both | v3 valid flag | v4 valid flag |
| --- | --- | --- | --- | --- |
| ADBE-FY2025-Q1-Q2~v3-contradictory_commentary | False | False | False | False |
| BOX-FY2025-Q1-Q2~v3-contradictory_commentary | False | True | False | True |
| INTU-FY2025-Q1-Q2~v3-contradictory_commentary | False | False | False | False |
| SNPS-FY2025-Q1-Q2~v3-contradictory_commentary | False | False | False | False |

## Remaining terminal failures

- 1: `metric_validation: nonliteral_evidence, nonliteral_horizon_evidence, unit_not_in_quote, quarterly_or_ambiguous_horizon, citation_not_in_retrieved_context`
- 1: `metric_validation: nonliteral_evidence, nonliteral_horizon_evidence, disconnected_horizon_evidence, unit_not_in_quote, quarterly_or_ambiguous_horizon, citation_not_in_retrieved_context`

## Saved traces

- [ADBE-FY2025-Q1-Q2](../earnings-v4-preflight-2026-10-15/runs/ADBE-FY2025-Q1-Q2_C.json)
- [ADBE-FY2025-Q1-Q2~v3-contradictory_commentary](../earnings-v4-preflight-2026-10-15/runs/ADBE-FY2025-Q1-Q2~v3-contradictory_commentary_C.json)
- [BOX-FY2025-Q1-Q2](../earnings-v4-preflight-2026-10-15/runs/BOX-FY2025-Q1-Q2_C.json)
- [BOX-FY2025-Q1-Q2~v3-contradictory_commentary](../earnings-v4-preflight-2026-10-15/runs/BOX-FY2025-Q1-Q2~v3-contradictory_commentary_C.json)
- [INTU-FY2025-Q1-Q2](../earnings-v4-preflight-2026-10-15/runs/INTU-FY2025-Q1-Q2_C.json)
- [INTU-FY2025-Q1-Q2~v3-contradictory_commentary](../earnings-v4-preflight-2026-10-15/runs/INTU-FY2025-Q1-Q2~v3-contradictory_commentary_C.json)
- [SNPS-FY2025-Q1-Q2](../earnings-v4-preflight-2026-10-15/runs/SNPS-FY2025-Q1-Q2_C.json)
- [SNPS-FY2025-Q1-Q2~v3-contradictory_commentary](../earnings-v4-preflight-2026-10-15/runs/SNPS-FY2025-Q1-Q2~v3-contradictory_commentary_C.json)

## Limits

- Four selected real development pairs and four synthetic derivatives, not eight independent events.
- Only C is rerun; B numbers are the existing v3 results on exactly matching sources.
- Batch handling and the C batching instruction changed; model, tool budget, retrieval ranking and validators stayed fixed.
- One run per case and version cannot isolate model variability or establish generalization.
- Synthetic contradiction wording is construction-known and does not establish natural-conflict detection.
- Real-case labels and semantic support judgments remain pending; literal validation is not entailment.
- Missing-evidence and stale controls were not rerun in v4; earlier counts must not be attributed to v4.
- Reported token cost uses peak cache-miss rates, ignores discounts, and is not a provider invoice.

## Reproduce

From the repository root:

```sh
python scripts/analyze_earnings_protocol_v4.py reports/earnings-v4-preflight-2026-10-15 --out reports/earnings-v4-analysis-2026-10-15 --check
```
