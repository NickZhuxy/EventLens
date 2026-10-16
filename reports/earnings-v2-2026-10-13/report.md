# Earnings investigation benchmark v2

Saved runs: 440 / 440. Real quarterly pairs: 36 (12 development, 24 held out); 12 issuers. Synthetic held-out controls: 72; natural supplements: 2.

Human-reviewed labels: 0. Unreviewed cases do not contribute to accuracy. Model-selected explanation support remains pending human review.

Costs use peak, cache-miss prices and include retained reservations for uncertain requests. These are conservative token estimates, not a provider invoice.

| Method | Split | Control | n | Numeric outputs | Abstain | Conflict | Expected status | Both expected citations | Calls |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A | development | real | 12 | 5 | 7 | 0 | unmeasured | unmeasured | 0 |
| A | heldout | real | 24 | 2 | 22 | 0 | unmeasured | unmeasured | 0 |
| A | supplemental_natural | real | 2 | 0 | 2 | 0 | unmeasured | unmeasured | 0 |
| A | synthetic_heldout | contradictory_commentary | 24 | 2 | 0 | 24 | 100.0% | 100.0% | 0 |
| A | synthetic_heldout | missing_table | 24 | 0 | 24 | 0 | 100.0% | unmeasured | 0 |
| A | synthetic_heldout | stale_disclosure | 24 | 0 | 24 | 0 | 100.0% | unmeasured | 0 |
| B | development | real | 12 | 5 | 7 | 0 | unmeasured | unmeasured | 12 |
| B | heldout | real | 24 | 4 | 20 | 0 | unmeasured | unmeasured | 24 |
| B | supplemental_natural | real | 2 | 0 | 2 | 0 | unmeasured | unmeasured | 2 |
| B | synthetic_heldout | contradictory_commentary | 24 | 2 | 22 | 2 | 8.3% | 8.3% | 24 |
| B | synthetic_heldout | missing_table | 24 | 0 | 24 | 0 | 100.0% | unmeasured | 24 |
| B | synthetic_heldout | stale_disclosure | 24 | 0 | 24 | 0 | 100.0% | unmeasured | 0 |
| C | development | real | 12 | 4 | 8 | 0 | unmeasured | unmeasured | 38 |
| C | heldout | real | 24 | 4 | 20 | 0 | unmeasured | unmeasured | 76 |
| C | supplemental_natural | real | 2 | 0 | 2 | 0 | unmeasured | unmeasured | 11 |
| C | synthetic_heldout | contradictory_commentary | 24 | 2 | 22 | 1 | 4.2% | 4.2% | 57 |
| C | synthetic_heldout | missing_table | 24 | 0 | 24 | 0 | 100.0% | unmeasured | 74 |
| C | synthetic_heldout | stale_disclosure | 24 | 0 | 24 | 0 | 100.0% | unmeasured | 0 |
| D | development | real | 12 | 5 | 7 | 0 | unmeasured | unmeasured | 0 |
| D | heldout | real | 24 | 14 | 10 | 0 | unmeasured | unmeasured | 0 |
| D | supplemental_natural | real | 2 | 0 | 2 | 0 | unmeasured | unmeasured | 0 |
| D | synthetic_heldout | contradictory_commentary | 24 | 14 | 7 | 17 | 70.8% | 70.8% | 0 |
| D | synthetic_heldout | missing_table | 24 | 0 | 24 | 0 | 100.0% | unmeasured | 0 |
| D | synthetic_heldout | stale_disclosure | 24 | 0 | 24 | 0 | 100.0% | unmeasured | 0 |

## Interpretation

The synthetic contradictory sentences are invented controls. Literal citations are validated against the saved source and, for C, the text actually retrieved. A model conflict flag on natural text is still a semantic-review candidate.
The missing-table variant masks all numeric tokens throughout the new disclosure, including duplicate prose, actuals and headings. It tests missing numerical evidence; it does not isolate table parsing. Stale pairs fail before model access.
A and D retain their frozen extraction rules. All four methods use the same original literal/semantic screen and Decimal arithmetic. The screen can reject valid complex layouts. B/C use one model and common extraction instructions; C has more calls and retrieves context. This is not compute matched.
The two natural supplements are development-issuer diagnostics, outside the 36 quarterly pairs. Unit/scope changes in the real corpus require human labels before their correctness can be scored.
A historical disclosure cutoff does not remove training-data exposure. This benchmark measures extraction and evidence discipline, not leakage-free investment performance.

See summary.json, runs/, requests/, sources.json, jobs.json and freeze.json for the complete record. Replay uses recorded responses and makes no network calls.
