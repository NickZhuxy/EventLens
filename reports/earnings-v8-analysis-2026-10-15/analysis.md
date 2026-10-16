# V8 corpus regression and table-row ablation

Full existing corpus regression and pipe-table-row-only ablation; no fresh blind test or human-reviewed accuracy.

Saved **288 / 288 run outcomes**, **333 request attempts**, **USD 0.9273147** conservative cost including retained reservations. **0 request(s) remain billing-uncertain** and are preserved as terminal failures, never retried. Every saved request, failure and result replays exactly. All A/D original comparisons match v2.

## Four-method coverage

| Method | Original split | Input | n | Numeric outputs | No terminal errors | Calls |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| A | development | real | 12 | 5 | 12 | 0 |
| A | heldout | real | 24 | 2 | 24 | 0 |
| A | synthetic_development | table_rows_only | 12 | 2 | 12 | 0 |
| A | synthetic_heldout | table_rows_only | 24 | 0 | 24 | 0 |
| B | development | real | 12 | 11 | 12 | 12 |
| B | heldout | real | 24 | 15 | 21 | 24 |
| B | synthetic_development | table_rows_only | 12 | 5 | 12 | 12 |
| B | synthetic_heldout | table_rows_only | 24 | 12 | 21 | 24 |
| C | development | real | 12 | 11 | 12 | 39 |
| C | heldout | real | 24 | 15 | 24 | 84 |
| C | synthetic_development | table_rows_only | 12 | 5 | 12 | 48 |
| C | synthetic_heldout | table_rows_only | 24 | 12 | 24 | 91 |
| D | development | real | 12 | 5 | 12 | 0 |
| D | heldout | real | 24 | 14 | 24 | 0 |
| D | synthetic_development | table_rows_only | 12 | 3 | 12 | 0 |
| D | synthetic_heldout | table_rows_only | 24 | 11 | 24 | 0 |

These are output counts, not accuracy. A completed abstention may still miss evidence. The original split is retained for comparison, without calling these cases unseen.

## Shared-parser control

| Original split | Input | n | Deterministic numerical outputs |
| --- | --- | ---: | ---: |
| development | real | 12 | 11 |
| heldout | real | 24 | 15 |
| synthetic_development | table_rows_only | 12 | 5 |
| synthetic_heldout | table_rows_only | 24 | 12 |

This control directly compares the unique parser candidates without a model. It makes deterministic assistance visible rather than assigning all numerical gains to the agent. Ambiguous/missing candidate sets abstain.

## Original and ablated case pairs

| Pair | Original split | A original / ablated | B original / ablated | C original / ablated | D original / ablated |
| --- | --- | --- | --- | --- | --- |
| ADBE-FY2025-Q2-Q3 | development | yes / no | yes / no | yes / no | yes / no |
| CRM-FY2024-Q1-Q2 | heldout | no / no | yes / yes | yes / yes | yes / yes |
| ADSK-FY2026-Q1-Q2 | heldout | yes / no | yes / no | yes / no | yes / no |
| ADBE-FY2025-priorQ4-Q1 | development | yes / no | yes / no | yes / no | no / no |
| ADBE-FY2025-Q1-Q2 | development | yes / no | yes / no | yes / no | yes / no |
| CRM-FY2024-priorQ4-Q1 | heldout | no / no | yes / yes | yes / yes | yes / yes |
| CRM-FY2024-Q2-Q3 | heldout | no / no | yes / yes | yes / yes | no / no |
| ADSK-FY2026-priorQ4-Q1 | heldout | no / no | yes / no | yes / no | yes / no |
| ADSK-FY2026-Q2-Q3 | heldout | yes / no | yes / no | yes / no | yes / no |
| INTU-FY2025-priorQ4-Q1 | development | no / no | yes / yes | yes / yes | yes / yes |
| INTU-FY2025-Q1-Q2 | development | no / no | yes / yes | yes / yes | yes / yes |
| INTU-FY2025-Q2-Q3 | development | no / no | yes / yes | yes / yes | yes / yes |
| SNPS-FY2025-priorQ4-Q1 | development | no / no | yes / no | yes / no | no / no |
| SNPS-FY2025-Q1-Q2 | development | no / no | yes / no | yes / no | no / no |
| SNPS-FY2025-Q2-Q3 | development | no / no | yes / no | yes / no | no / no |
| BOX-FY2025-priorQ4-Q1 | development | yes / yes | yes / yes | yes / yes | no / no |
| BOX-FY2025-Q1-Q2 | development | yes / yes | yes / yes | yes / yes | no / no |
| BOX-FY2025-Q2-Q3 | development | no / no | no / no | no / no | no / no |
| CDNS-FY2025-priorQ4-Q1 | heldout | no / no | yes / yes | yes / yes | yes / yes |
| CDNS-FY2025-Q1-Q2 | heldout | no / no | yes / yes | yes / yes | yes / yes |
| CDNS-FY2025-Q2-Q3 | heldout | no / no | yes / yes | yes / yes | yes / yes |
| ZM-FY2025-priorQ4-Q1 | heldout | no / no | no / no | no / no | no / no |
| ZM-FY2025-Q1-Q2 | heldout | no / no | no / no | no / no | no / no |
| ZM-FY2025-Q2-Q3 | heldout | no / no | no / no | no / no | no / no |
| ZS-FY2025-priorQ4-Q1 | heldout | no / no | yes / yes | yes / yes | yes / yes |
| ZS-FY2025-Q1-Q2 | heldout | no / no | yes / yes | yes / yes | yes / yes |
| ZS-FY2025-Q2-Q3 | heldout | no / no | yes / yes | yes / yes | yes / yes |
| DDOG-FY2025-priorQ4-Q1 | heldout | no / no | no / no | no / no | no / no |
| DDOG-FY2025-Q1-Q2 | heldout | no / no | no / no | no / no | no / no |
| DDOG-FY2025-Q2-Q3 | heldout | no / no | no / no | no / no | no / no |
| OKTA-FY2025-priorQ4-Q1 | heldout | no / no | yes / yes | yes / yes | yes / yes |
| OKTA-FY2025-Q1-Q2 | heldout | no / no | yes / yes | yes / yes | yes / yes |
| OKTA-FY2025-Q2-Q3 | heldout | no / no | yes / yes | yes / yes | yes / yes |
| HUBS-FY2025-priorQ4-Q1 | heldout | no / no | no / no | no / no | no / no |
| HUBS-FY2025-Q1-Q2 | heldout | no / no | no / no | no / no | no / no |
| HUBS-FY2025-Q2-Q3 | heldout | no / no | no / no | no / no | no / no |

## Failures and review

Terminal errors: {"metric_id_not_in_retrieved_context": 5, "prior_uncertain_request_not_retried": 1}.

Every B/C error, rejected action, comparability warning, unresolved narrative, explanation and conflict is retained in `model_diagnostics` in the JSON report. These model judgments remain unreviewed. Full traces are in the sibling execution bundle.

## Limits

- The 24 originally held-out pairs are now-exposed regression cases, not fresh unseen validation.
- B/C share a bounded candidate parser and source-reference interface; A/D retain earlier extraction rules. This is a system comparison, not an isolated agent-reasoning comparison.
- The deterministic shared-parser control separates candidate availability from model selection. Its outputs are not ground truth.
- Table ablation deletes pipe-bearing physical rows only. Non-pipe header continuations and every prose number remain. Surviving prose can legitimately support guidance; blanket abstention is not the expected answer.
- All labels and model explanation/conflict judgments remain pending Nick. Literal matches and Decimal arithmetic do not validate free-form prose.
- Single samples cannot establish stability or superiority. All unsuccessful outputs are retained.
- Token costs use conservative peak/cache-miss rates, not an invoice; the hard cap can stop an incomplete run.

## Reproduce

```sh
python scripts/analyze_earnings_expansion_v8.py --check
```
