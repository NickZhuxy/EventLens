# V5 table and conflict pilot

Four exposed development pairs and twelve synthetic derivatives, both B/C. Operational counts, not reviewed accuracy or unseen validation.

Completed **32 B/C runs** and **64 requests**, with **USD 0.1967478** conservative token cost under the approved USD 5.50 cap. Zero uncertain requests. Combined v3/v4/v5 cost: **USD 0.5377650**, within the prior USD 6 allocation. All v3/v4/v5 requests and outputs replay exactly offline.

## Matched operational results

| Version | Method | Case type | n | No terminal errors | Numerical outputs | Valid control outcomes | Calls |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| v3 | B | contradictory_commentary | 4 | 2 | 2 | 1 | 4 |
| v3 | B | missing_numerical_evidence | 4 | 1 | 0 | 1 | 4 |
| v3 | B | real | 4 | 2 | 2 | unreviewed | 4 |
| v3 | B | stale_disclosure | 4 | 0 | 0 | 4 | 0 |
| v3 | C | contradictory_commentary | 4 | 3 | 2 | 0 | 32 |
| v3 | C | missing_numerical_evidence | 4 | 2 | 0 | 2 | 25 |
| v3 | C | real | 4 | 3 | 2 | unreviewed | 25 |
| v3 | C | stale_disclosure | 4 | 0 | 0 | 4 | 0 |
| v4 | C | contradictory_commentary | 4 | 3 | 2 | 1 | 24 |
| v4 | C | real | 4 | 3 | 3 | unreviewed | 19 |
| v5 | B | contradictory_commentary | 4 | 0 | 0 | 0 | 4 |
| v5 | B | missing_numerical_evidence | 4 | 4 | 0 | 4 | 4 |
| v5 | B | real | 4 | 4 | 4 | unreviewed | 4 |
| v5 | B | stale_disclosure | 4 | 0 | 0 | 4 | 0 |
| v5 | C | contradictory_commentary | 4 | 0 | 0 | 0 | 23 |
| v5 | C | missing_numerical_evidence | 4 | 4 | 0 | 4 | 14 |
| v5 | C | real | 4 | 4 | 4 | unreviewed | 15 |
| v5 | C | stale_disclosure | 4 | 0 | 0 | 4 | 0 |

A numerical output is not an accuracy judgment. Valid controls exclude terminal failures; stale guards intentionally return errors before inference. V4 reran only C real/contradiction cases.

## Parser availability and model selection

B receives full sources plus the same catalogs available to C. The following candidates exist deterministically before inference. Their proof details and every selected ID are saved in `analysis.json` and the raw runs.

| Real pair | Old / new candidates | Proof kinds | B numerical output | C numerical output |
| --- | --- | --- | --- | --- |
| ADBE-FY2025-Q1-Q2 | 1 / 1 | legacy_literal_screen | True | True |
| INTU-FY2025-Q1-Q2 | 1 / 1 | legacy_literal_screen | True | True |
| SNPS-FY2025-Q1-Q2 | 1 / 1 | explicit_annual_column | True | True |
| BOX-FY2025-Q1-Q2 | 1 / 1 | legacy_literal_screen | True | True |

Required reviews completed: **24/24 eligible B/C runs**. B catalogs are supplied automatically; C completes actual read-only actions. Expected stale rejections: **8/8**, all before model access.

## Synthetic conflict retrieval

| Method | Controls | Both statements visible | Valid flags with both source-specific citations |
| --- | ---: | ---: | ---: |
| B | 4 | 4 | 0 |
| C | 4 | 4 | 0 |

These flags concern injected synthetic text. Natural explanation/conflict selections are retained in `natural_review_candidates`, with no manufactured human judgments.

All eight B/C contradiction runs failed `citation_id_not_in_retrieved_context` despite both injected statements being visible. The schema names `statement_a` and `statement_b` are plain strings, while the resolver expects evidence IDs. Rejected conflict entries contain quotation text in those fields. The saved rejected arguments are retained for diagnosis; they are not counted as successful flags. V5 remains frozen. A separate interface revision must use explicit ID fields and constrain choices to visible references.

## Operational diagnostics

Accepted multiple-function responses: **26/27**. Tokens: **588662 input / 16791 output**. Median eligible-run latency: **4.545 seconds**.

Eligible-case terminal errors: {"citation_id_not_in_retrieved_context": 8}

Validation failures (including recovered attempts): {"citation_id_not_in_retrieved_context": 15, "finish_required_at_budget_boundary": 1, "invalid character offsets": 1}

## Every paired outcome

| Case | Method | v3 / v4 / v5 numerical output | v5 terminal errors | v5 calls |
| --- | --- | --- | --- | ---: |
| [ADBE-FY2025-Q1-Q2](../earnings-v5-preflight-2026-10-15/runs/ADBE-FY2025-Q1-Q2_B.json) | B | True / not run / True | none | 1 |
| [ADBE-FY2025-Q1-Q2](../earnings-v5-preflight-2026-10-15/runs/ADBE-FY2025-Q1-Q2_C.json) | C | True / True / True | none | 4 |
| [ADBE-FY2025-Q1-Q2~v3-contradictory_commentary](../earnings-v5-preflight-2026-10-15/runs/ADBE-FY2025-Q1-Q2~v3-contradictory_commentary_B.json) | B | True / not run / False | citation_id_not_in_retrieved_context | 1 |
| [ADBE-FY2025-Q1-Q2~v3-contradictory_commentary](../earnings-v5-preflight-2026-10-15/runs/ADBE-FY2025-Q1-Q2~v3-contradictory_commentary_C.json) | C | True / True / False | citation_id_not_in_retrieved_context | 6 |
| [ADBE-FY2025-Q1-Q2~v3-missing_numerical_evidence](../earnings-v5-preflight-2026-10-15/runs/ADBE-FY2025-Q1-Q2~v3-missing_numerical_evidence_B.json) | B | False / not run / False | none | 1 |
| [ADBE-FY2025-Q1-Q2~v3-missing_numerical_evidence](../earnings-v5-preflight-2026-10-15/runs/ADBE-FY2025-Q1-Q2~v3-missing_numerical_evidence_C.json) | C | False / not run / False | none | 4 |
| [ADBE-FY2025-Q1-Q2~v3-stale_disclosure](../earnings-v5-preflight-2026-10-15/runs/ADBE-FY2025-Q1-Q2~v3-stale_disclosure_B.json) | B | False / not run / False | stale_or_reversed_disclosure_pair | 0 |
| [ADBE-FY2025-Q1-Q2~v3-stale_disclosure](../earnings-v5-preflight-2026-10-15/runs/ADBE-FY2025-Q1-Q2~v3-stale_disclosure_C.json) | C | False / not run / False | stale_or_reversed_disclosure_pair | 0 |
| [BOX-FY2025-Q1-Q2](../earnings-v5-preflight-2026-10-15/runs/BOX-FY2025-Q1-Q2_B.json) | B | True / not run / True | none | 1 |
| [BOX-FY2025-Q1-Q2](../earnings-v5-preflight-2026-10-15/runs/BOX-FY2025-Q1-Q2_C.json) | C | False / True / True | none | 3 |
| [BOX-FY2025-Q1-Q2~v3-contradictory_commentary](../earnings-v5-preflight-2026-10-15/runs/BOX-FY2025-Q1-Q2~v3-contradictory_commentary_B.json) | B | True / not run / False | citation_id_not_in_retrieved_context | 1 |
| [BOX-FY2025-Q1-Q2~v3-contradictory_commentary](../earnings-v5-preflight-2026-10-15/runs/BOX-FY2025-Q1-Q2~v3-contradictory_commentary_C.json) | C | True / True / False | citation_id_not_in_retrieved_context | 6 |
| [BOX-FY2025-Q1-Q2~v3-missing_numerical_evidence](../earnings-v5-preflight-2026-10-15/runs/BOX-FY2025-Q1-Q2~v3-missing_numerical_evidence_B.json) | B | False / not run / False | none | 1 |
| [BOX-FY2025-Q1-Q2~v3-missing_numerical_evidence](../earnings-v5-preflight-2026-10-15/runs/BOX-FY2025-Q1-Q2~v3-missing_numerical_evidence_C.json) | C | False / not run / False | none | 3 |
| [BOX-FY2025-Q1-Q2~v3-stale_disclosure](../earnings-v5-preflight-2026-10-15/runs/BOX-FY2025-Q1-Q2~v3-stale_disclosure_B.json) | B | False / not run / False | stale_or_reversed_disclosure_pair | 0 |
| [BOX-FY2025-Q1-Q2~v3-stale_disclosure](../earnings-v5-preflight-2026-10-15/runs/BOX-FY2025-Q1-Q2~v3-stale_disclosure_C.json) | C | False / not run / False | stale_or_reversed_disclosure_pair | 0 |
| [INTU-FY2025-Q1-Q2](../earnings-v5-preflight-2026-10-15/runs/INTU-FY2025-Q1-Q2_B.json) | B | False / not run / True | none | 1 |
| [INTU-FY2025-Q1-Q2](../earnings-v5-preflight-2026-10-15/runs/INTU-FY2025-Q1-Q2_C.json) | C | True / True / True | none | 4 |
| [INTU-FY2025-Q1-Q2~v3-contradictory_commentary](../earnings-v5-preflight-2026-10-15/runs/INTU-FY2025-Q1-Q2~v3-contradictory_commentary_B.json) | B | False / not run / False | citation_id_not_in_retrieved_context | 1 |
| [INTU-FY2025-Q1-Q2~v3-contradictory_commentary](../earnings-v5-preflight-2026-10-15/runs/INTU-FY2025-Q1-Q2~v3-contradictory_commentary_C.json) | C | False / False / False | citation_id_not_in_retrieved_context | 6 |
| [INTU-FY2025-Q1-Q2~v3-missing_numerical_evidence](../earnings-v5-preflight-2026-10-15/runs/INTU-FY2025-Q1-Q2~v3-missing_numerical_evidence_B.json) | B | False / not run / False | none | 1 |
| [INTU-FY2025-Q1-Q2~v3-missing_numerical_evidence](../earnings-v5-preflight-2026-10-15/runs/INTU-FY2025-Q1-Q2~v3-missing_numerical_evidence_C.json) | C | False / not run / False | none | 4 |
| [INTU-FY2025-Q1-Q2~v3-stale_disclosure](../earnings-v5-preflight-2026-10-15/runs/INTU-FY2025-Q1-Q2~v3-stale_disclosure_B.json) | B | False / not run / False | stale_or_reversed_disclosure_pair | 0 |
| [INTU-FY2025-Q1-Q2~v3-stale_disclosure](../earnings-v5-preflight-2026-10-15/runs/INTU-FY2025-Q1-Q2~v3-stale_disclosure_C.json) | C | False / not run / False | stale_or_reversed_disclosure_pair | 0 |
| [SNPS-FY2025-Q1-Q2](../earnings-v5-preflight-2026-10-15/runs/SNPS-FY2025-Q1-Q2_B.json) | B | False / not run / True | none | 1 |
| [SNPS-FY2025-Q1-Q2](../earnings-v5-preflight-2026-10-15/runs/SNPS-FY2025-Q1-Q2_C.json) | C | False / False / True | none | 4 |
| [SNPS-FY2025-Q1-Q2~v3-contradictory_commentary](../earnings-v5-preflight-2026-10-15/runs/SNPS-FY2025-Q1-Q2~v3-contradictory_commentary_B.json) | B | False / not run / False | citation_id_not_in_retrieved_context | 1 |
| [SNPS-FY2025-Q1-Q2~v3-contradictory_commentary](../earnings-v5-preflight-2026-10-15/runs/SNPS-FY2025-Q1-Q2~v3-contradictory_commentary_C.json) | C | False / False / False | citation_id_not_in_retrieved_context | 5 |
| [SNPS-FY2025-Q1-Q2~v3-missing_numerical_evidence](../earnings-v5-preflight-2026-10-15/runs/SNPS-FY2025-Q1-Q2~v3-missing_numerical_evidence_B.json) | B | False / not run / False | none | 1 |
| [SNPS-FY2025-Q1-Q2~v3-missing_numerical_evidence](../earnings-v5-preflight-2026-10-15/runs/SNPS-FY2025-Q1-Q2~v3-missing_numerical_evidence_C.json) | C | False / not run / False | none | 3 |
| [SNPS-FY2025-Q1-Q2~v3-stale_disclosure](../earnings-v5-preflight-2026-10-15/runs/SNPS-FY2025-Q1-Q2~v3-stale_disclosure_B.json) | B | False / not run / False | stale_or_reversed_disclosure_pair | 0 |
| [SNPS-FY2025-Q1-Q2~v3-stale_disclosure](../earnings-v5-preflight-2026-10-15/runs/SNPS-FY2025-Q1-Q2~v3-stale_disclosure_C.json) | C | False / not run / False | stale_or_reversed_disclosure_pair | 0 |

## Limits

- Selection was based on prior development failures. No new held-out or independent company events.
- V5 changes table parsing, evidence references, retrieval ranking and mandatory review together. One sample per case cannot isolate their effects or model variability.
- Both B and C use the same deterministic candidate catalogs. Numerical gains cannot be credited solely to agent reasoning; a general advantage over B or D is unestablished.
- The contradiction controls contain construction-known opposite-polarity sentences. They do not establish detection of natural management conflicts.
- The missing-evidence control masks all numerical tokens, including prose and years. It is not table-only deletion.
- Stale controls stop before inference. Their expected guard errors are distinct from eligible-case operational failures.
- All 36 natural labels and human semantic support judgments remain pending. Literal offsets and structural proofs do not establish semantic accuracy.
- V5 remains an opt-in versioned experiment; the original four-method held-out benchmark and default CLI are unchanged.
- Cost uses peak cache-miss token rates and ignores discounts; it is not a provider invoice.

## Reproduce

```sh
python scripts/analyze_earnings_protocol_v5.py reports/earnings-v5-preflight-2026-10-15 --out reports/earnings-v5-analysis-2026-10-15 --check
```
