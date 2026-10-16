# V7: corpus regression and table-row ablation

This experiment applies the frozen v6 B/C controller to all 36 existing disclosure pairs, alongside the unchanged A rule and D document-diff baselines. It also runs all four methods on a table-row-only derivative of each current disclosure: 72 case/variant pairs and 288 method runs. The original 12 development / 24 held-out split remains visible. Those held-out inputs have already been exposed; this is regression evidence, not a new blind test.

## Exact transformation

The [runner](../scripts/earnings_expansion_v7.py) removes the contents of physical lines containing pipe separators from the new disclosure and retains their newlines. All other characters remain unchanged, including prose numbers, year headings and any non-pipe continuation lines inside multiline headers. Each removed span is saved with original offsets and text. Source IDs, derivative hashes and parent hashes travel with every job.

This is a normalized pipe-table-row ablation. It does not reconstruct or delete original HTML tables. It differs from the older broad mask, which removed every numerical token throughout the disclosure. An annual range may survive in prose, so a numerical output can be appropriate after table removal. No blanket abstention expectation or accuracy label is assigned by the transformation.

## Method and scoring boundaries

A and D retain their frozen extraction rules and literal validator. B and C share the v5 candidate parser and v6 reference-choice interface. B sees full sources and the same catalogs that C retrieves; C retains its eight-call/seven-retrieval budget. This compares systems with different deterministic assistance, not just agent reasoning. The analysis separately computes a shared-parser control without a model.

Output coverage, operational failures, source-bound references and ablation effects are measurable without human labels. Correctness of ranges, guidance decisions and semantic explanations still requires Nick. Failed model calls are not successful abstentions. Original A/D comparisons must exactly match the saved v2 results.

## Budget

The [estimate](../reports/earnings-v7-2026-10-15/estimate.json) extrapolates the observed v5 cost per eligible B+C pair: **USD 1.1804868** for 72 pairs/variants. The hard cap is **USD 3.25**, allocated under Nick's continuing authorization to preserve USD 0.50 of the current USD 6 budget. Prior v3–v6 spend is USD 0.5947704.

The unconstrained worst case is 648 maximum-size requests at USD 30.3450624; this amount is not authorized. A reserve is written before every request, and the hard cap stops the experiment before an unaffordable request. A budget stop must be reported as an incomplete experiment. A shared execution lock prevents concurrent allocations; prior incomplete or uncertain charges cannot be silently reused. These figures are conservative peak/cache-miss token estimates, not a provider balance or invoice.

## Reproduction and review

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
python scripts/analyze_earnings_expansion_v7.py --check
python scripts/prepare_earnings_review_v7.py --check
python scripts/earnings_budget.py
```

The [pending review file](../reports/earnings-v7-review-2026-10-15/labels.pending.json) contains machine suggestions for 24 pairs with two unique candidates and leaves missing/ambiguous sides blank. All 36 pairs remain pending, with no reviewer, timestamp or attestation. The builder preserves the original draft dataset and does not change browser storage. Export a backup before restoring this JSON in the existing disclosure review page. Review the source, units, period, bounds and explanations yourself before marking a pair reviewed.

The corpus, prior paid results, v6 controller and source snapshots remain frozen. No résumé accuracy claim or remote CI result follows from this execution alone.

## Completed result

[All 288 outcomes and 356 request attempts replay exactly](../reports/earnings-v7-analysis-2026-10-15/analysis.md). Conservative cost is USD 1.0209237, including one USD 0.0374805 uncertain reservation. The provider failure is retained. A separately recorded continuation executed only previously unattempted cases, never resent the failed request, and verified that every prior request/run stayed unchanged. C produced numerical outputs on 14/24 original held-out real pairs, with no terminal controller errors. These cases are now exposed regression data; the count is not accuracy.
