# EventLens evaluation

All accuracy results below are provisional against AI-drafted labels. Nick has not reviewed these labels.

Corpus: 6 normalized public source snapshots; 3 eligible same-horizon real pairs; 3 issuers.
Synthetic controls are counted separately. No live model evaluation was run unless the methods list explicitly says live.

| Method | Split | Cases | Precision | Recall | Numeric errors / emitted | Abstentions | Calls |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| A | development | 1 | 1.000 | 1.000 | 0 / 1 | 0 | 0 |
| A | heldout | 2 | 1.000 | 0.500 | 0 / 1 | 1 | 0 |
| A | synthetic_development | 9 | unmeasured | unmeasured | None / 2 | 6 | 0 |

## Method status

- A: executed deterministic rules
- B: not_run_no_live_model
- C: not_run_no_live_model

## Interpretation and limits

A match requires the source, issuer, metric, currency, basis, fiscal horizon, definition, status and normalized bounds to agree. Equivalent million/billion units count as equal. Precision includes all emitted candidates, including candidates rejected by the evidence screen.
Numerical errors are counted only when a calculation is emitted. Missed comparisons and extraction false negatives remain visible; zero arithmetic errors does not mean all cases succeeded.
Literal evidence checks and lexical semantic screens are automated. Human evidence-support errors are unmeasured. Management explanations are review candidates; no verified causal decomposition is claimed.
The three real pairs are a convenience sample of upward revisions. They do not estimate broad financial extraction performance. The issuer split was set before held-out runs, but source selection and labels used AI assistance and were not blinded.
The snapshots were retrieved in 2026. The disclosure cutoff is a date-based replay assumption, with date-only publications set conservatively to end of day in New York. It does not prove historical byte availability. Use --cutoff-mode snapshot for a strict retrieval-time bound; these old cutoffs then abstain.
The Autodesk Q2 FY2026 capture contains its main release and outlook but only part of the financial appendix because subsequent retrieval returned HTTP 403. See data/capture_audit.json. Quotes are checked against saved normalized text, not the original HTML byte stream.
B receives the complete saved pair snapshots in one call. C starts with metadata and selects bounded read-only retrieval calls over the same pair. The model, cutoff and questions are shared. Context and call budgets differ and are recorded; this is not a compute-matched comparison.
Calls and latency are measured per run. Missing provider token usage is null, never zero. Mock controller tests are engineering checks and are excluded from the real evaluation.

## Abstentions and conflict flags

- CRM-FY2024-Q1-Q2 (A): insufficient_evidence — missing_guidance
- ADBE-FY2025-Q2-Q3~missing_table (A): insufficient_evidence — missing_guidance
- ADBE-FY2025-Q2-Q3~mismatched_units (A): insufficient_evidence — missing_guidance
- ADBE-FY2025-Q2-Q3~unknown_units (A): insufficient_evidence — missing_guidance
- ADBE-FY2025-Q2-Q3~incompatible_horizon (A): insufficient_evidence — missing_guidance
- ADBE-FY2025-Q2-Q3~contradictory_explanations (A): conflicting — opposing_explicit_demand_statements
- ADBE-FY2025-Q2-Q3~conflicting_ranges (A): conflicting — conflicting_guidance_ranges
- ADBE-FY2025-Q2-Q3~stale_disclosure (A): insufficient_evidence — stale_or_reversed_disclosure_pair
- ADBE-FY2025-Q2-Q3~early_cutoff (A): insufficient_evidence — source_after_cutoff

See summary.json, runs/*.json, review_queue.json, and provenance.json in this directory for the raw evidence.
