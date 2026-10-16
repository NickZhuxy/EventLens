# Earnings evidence checkpoint

Engineering evidence for the earnings implementation; zero human-reviewed labels. Numerical accuracy and natural semantic support remain unestablished.

The corpus contains 36 disclosure pairs from 12 issuers. All 36 labels remain pending human review.

## Current corpus regression

The originally held-out 24 pairs are now exposed regression cases. Numerical outputs are coverage, not accuracy. B/C use the same candidate parser; the A/D extraction rules remain unchanged.

| Method | n | Numerical outputs | No terminal errors |
| --- | ---: | ---: | ---: |
| A | 24 | 2 | 24 |
| B | 24 | 15 | 21 |
| C | 24 | 15 | 24 |
| D | 24 | 14 | 24 |

## Stress controls

| Control | Method | n | Valid outcomes | Failed attempts |
| --- | --- | ---: | ---: | ---: |
| stale_disclosure | A | 24 | 24 | 0 |
| stale_disclosure | B | 24 | 24 | 0 |
| stale_disclosure | C | 24 | 24 | 0 |
| stale_disclosure | D | 24 | 24 | 0 |
| missing_table | A | 24 | 24 | 0 |
| missing_table | B | 24 | 22 | 2 |
| missing_table | C | 24 | 24 | 0 |
| missing_table | D | 24 | 24 | 0 |
| contradictory_commentary | A | 24 | 24 | 0 |
| contradictory_commentary | B | 24 | 21 | 3 |
| contradictory_commentary | C | 24 | 24 | 0 |
| contradictory_commentary | D | 24 | 17 | 0 |

The original `missing_table` control removes all numbers. [V8](../earnings-v8-analysis-2026-10-15/analysis.md) separately deletes only pipe-bearing table rows while preserving prose. Surviving prose may support a numerical output. Synthetic opposite-polarity statements do not establish natural management-conflict accuracy.

## Cost and latency

| Version | Method | Split | Input | n | Provider requests | Cost incl. reservations, USD | Median seconds |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| 7 | A | development | real | 12 | 0 | 0 | 0.002 |
| 7 | A | heldout | real | 24 | 0 | 0 | 0.002 |
| 7 | A | synthetic_development | table_rows_only | 12 | 0 | 0 | 0.002 |
| 7 | A | synthetic_heldout | table_rows_only | 24 | 0 | 0 | 0.001 |
| 7 | B | development | real | 12 | 12 | 0.1202286 | 3.394 |
| 7 | B | heldout | real | 24 | 24 | 0.2334933 | 3.281 |
| 7 | B | synthetic_development | table_rows_only | 12 | 12 | 0.0874344 | 3.527 |
| 7 | B | synthetic_heldout | table_rows_only | 24 | 24 | 0.1526148 | 3.489 |
| 7 | C | development | real | 12 | 41 | 0.0621771 | 6.59 |
| 7 | C | heldout | real | 24 | 90 | 0.1302252 | 6.364 |
| 7 | C | synthetic_development | table_rows_only | 12 | 50 | 0.0785127 | 7.48 |
| 7 | C | synthetic_heldout | table_rows_only | 24 | 103 | 0.1562376 | 7.862 |
| 7 | D | development | real | 12 | 0 | 0 | 0.009 |
| 7 | D | heldout | real | 24 | 0 | 0 | 0.007 |
| 7 | D | synthetic_development | table_rows_only | 12 | 0 | 0 | 0.006 |
| 7 | D | synthetic_heldout | table_rows_only | 24 | 0 | 0 | 0.005 |
| 8 | A | development | real | 12 | 0 | 0 | 0.002 |
| 8 | A | heldout | real | 24 | 0 | 0 | 0.002 |
| 8 | A | synthetic_development | table_rows_only | 12 | 0 | 0 | 0.002 |
| 8 | A | synthetic_heldout | table_rows_only | 24 | 0 | 0 | 0.001 |
| 8 | B | development | real | 12 | 12 | 0.1203399 | 3.121 |
| 8 | B | heldout | real | 24 | 23 | 0.1962753 | 3.142 |
| 8 | B | synthetic_development | table_rows_only | 12 | 12 | 0.0875805 | 3.33 |
| 8 | B | synthetic_heldout | table_rows_only | 24 | 24 | 0.1519671 | 3.187 |
| 8 | C | development | real | 12 | 39 | 0.0602283 | 6.331 |
| 8 | C | heldout | real | 24 | 84 | 0.1123236 | 6.524 |
| 8 | C | synthetic_development | table_rows_only | 12 | 48 | 0.0738744 | 7.308 |
| 8 | C | synthetic_heldout | table_rows_only | 24 | 91 | 0.1247256 | 6.953 |
| 8 | D | development | real | 12 | 0 | 0 | 0.009 |
| 8 | D | heldout | real | 24 | 0 | 0 | 0.007 |
| 8 | D | synthetic_development | table_rows_only | 12 | 0 | 0 | 0.006 |
| 8 | D | synthetic_heldout | table_rows_only | 24 | 0 | 0 | 0.005 |
| 9 | A | supplemental_natural | real | 2 | 0 | 0 | 0.001 |
| 9 | A | synthetic_heldout | contradictory_commentary | 24 | 0 | 0 | 0.002 |
| 9 | A | synthetic_heldout | missing_table | 24 | 0 | 0 | 0.002 |
| 9 | A | synthetic_heldout | stale_disclosure | 24 | 0 | 0 | 0.0 |
| 9 | B | supplemental_natural | real | 2 | 2 | 0.0142185 | 3.752 |
| 9 | B | synthetic_heldout | contradictory_commentary | 24 | 24 | 0.2117517 | 3.959 |
| 9 | B | synthetic_heldout | missing_table | 24 | 22 | 0.1943616 | 3.611 |
| 9 | B | synthetic_heldout | stale_disclosure | 24 | 0 | 0 | 0.0 |
| 9 | C | supplemental_natural | real | 2 | 7 | 0.0085455 | 6.826 |
| 9 | C | synthetic_heldout | contradictory_commentary | 24 | 92 | 0.1413942 | 7.684 |
| 9 | C | synthetic_heldout | missing_table | 24 | 91 | 0.1318983 | 7.043 |
| 9 | C | synthetic_heldout | stale_disclosure | 24 | 0 | 0 | 0.0 |
| 9 | D | supplemental_natural | real | 2 | 0 | 0 | 0.004 |
| 9 | D | synthetic_heldout | contradictory_commentary | 24 | 0 | 0 | 0.007 |
| 9 | D | synthetic_heldout | missing_table | 24 | 0 | 0 | 0.006 |
| 9 | D | synthetic_heldout | stale_disclosure | 24 | 0 | 0 | 0.0 |

Improvement allocation: USD 6.00. Used or conservatively reserved: USD 3.2451786. Remaining in that allocation: USD 2.7548214; further authorized spend after preserving USD 0.50: USD 2.2548214.

These are peak/cache-miss token estimates and retained uncertain charges, not a provider account balance or invoice. The earlier v2 benchmark uses a separate allocation. Controller attempts can include a blocked request that never reached the provider. Failed attempts remain in all denominators.

## Inspect and reproduce

- [Explicit conflict references: v6](../earnings-v6-analysis-2026-10-15/analysis.md)
- [Full corpus and table ablation: v7](../earnings-v7-analysis-2026-10-15/analysis.md)
- [Point-target screening: v8](../earnings-v8-analysis-2026-10-15/analysis.md)
- [Full stress regression: v9](../earnings-v9-analysis-2026-10-15/analysis.md)
- [Recomputed BOX arithmetic](../earnings-examples-2026-10-15/box-arithmetic.md)
- [Synthetic conflict with annual table evidence](../earnings-examples-2026-10-15/synopsys-synthetic-conflict.md)
- [Pending review suggestions](../earnings-v8-review-2026-10-15/labels.pending.json)

A separate [semantic review sample](../earnings-v8-review-2026-10-15/semantic-review.pending.json) contains 33 pending natural explanation/conflict candidates. The sole natural B conflict candidate has a [field/reason inconsistency](../earnings-v8-review-2026-10-15/natural-conflict-note.json); C emitted no natural conflict in the original 24 held-out real pairs.

```sh
python scripts/earnings_evidence_index.py --check
```

## Remaining acceptance requirements

- Nick must review all 36 labels before precision, recall, direction or exact-match accuracy is reported.
- Natural explanation support and natural conflicts still require human semantic review.
- All original held-out inputs have now been exposed. Any new generalization claim needs a separately frozen unseen set.
- Remote CI and publication require an authorized push. No push was made.
