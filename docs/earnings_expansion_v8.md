# V8: distinguish revenue targets from monetary impacts

V8 retains the v6 evidence-selection protocol and adds one conservative filter to the v5 candidate catalog. In the Adobe development disclosure, the old parser admitted an approximate USD 200 million foreign-exchange headwind as an absolute annual revenue target. The same source also contains the actual USD 23.30–23.55 billion range. A monetary impact is not a total-revenue forecast.

The [new evidence module](../src/eventlens/evidence_v8.py) preserves explicit ranges. For a single point target, it requires the revenue noun before the matching amount and rejects impact/change language immediately around that amount. Unsupported point syntax abstains. It does not infer a replacement number. Existing valid candidate IDs stay unchanged. The frozen v5 module and all earlier outputs remain intact.

The [configuration](../configs/earnings_expansion_v8.json) uses exactly the same 36 real pairs and 36 pipe-table-row derivatives as v7, with A/B/C/D: 288 outcomes. A/D retain their original rules. B/C share the new parser. This is a paired system regression on previously exposed data, not a blind test or an isolated test of agent reasoning. The change was motivated by Adobe development data before inspection of v7 held-out case diagnoses.

The planning estimate is USD 1.1804868, with a USD 1.50 hard cap under the continuing USD 6 allocation and USD 0.50 reserve. The much larger unconstrained estimate is not authorized; the journal stops before an unaffordable request. The frozen v7 billing-uncertain request remains fully reserved. V8 refuses an identical request envelope before model access and retains that blocked outcome in its denominator.

## Inspect and reproduce

The [analysis](../reports/earnings-v8-analysis-2026-10-15/analysis.md) includes the parser-only control, all outcomes, exact v7/v8 case matching, rejected point candidates, and the unchanged A/D comparison with v2. Free-form model explanation accuracy remains unmeasured.

```sh
python scripts/analyze_earnings_expansion_v8.py --check
python scripts/verify_earnings_protocol_v8.py reports/earnings-v8-2026-10-15 \
  --out reports/earnings-v8-validation-2026-10-15/scripted --check
python scripts/prepare_earnings_review_v8.py --check
```

The scripted traces are explicitly labeled fixtures, not model results. The [review suggestions](../reports/earnings-v8-review-2026-10-15/labels.pending.json) supply two unique metric drafts for 26 pairs. Every one of the 36 pairs remains pending, with no reviewer, timestamp or attestation. Back up any existing review export before using **Restore review JSON** in the local review page. No browser storage or original draft label was changed by the suggestion builder.

## Numerical presentation

The offline [case report generator](../scripts/earnings_case_report.py) recomputes arithmetic from accepted metric records. It rejects a modified calculation and preserves missing values. The [BOX example](../reports/earnings-examples-2026-10-15/box-arithmetic.md) therefore displays lower/upper increases of USD 11 million and USD 10 million, without repeating the erroneous model narrative from its saved v5 trace. Model notes remain available for semantic review in the complete trace. This presentation safeguard does not retrospectively make the model prose correct.

## Completed result

All 288 outcomes and 333 provider requests replay exactly at USD 0.9273147 conservative token cost. There are no new uncertain charges. One attempted B envelope matched the earlier uncertain request and was blocked locally, with no new request record or charge. Its failed outcome remains in the denominator. C produced numerical comparisons on 15/24 original held-out real pairs and 12/24 corresponding table-row ablations, with no terminal controller errors. D produced 14/24 and 11/24 respectively. These are coverage counts with different parser assistance, not reviewed correctness or superiority.

## Semantic review

The [new semantic review queue](../reports/earnings-v8-review-2026-10-15/semantic-review.pending.json) samples 33 emitted natural candidates by deterministic hash order: eight explanations per method, plus one B conflict candidate. All judgments remain pending. C emitted no natural conflict candidate in the original 24 held-out real pairs. The [B candidate note](../reports/earnings-v8-review-2026-10-15/natural-conflict-note.json) preserves a field/reason inconsistency: the record places a guidance revision in the conflict array while its reason says it is only a guidance update, not a conflict. It is not evidence of a validated natural management contradiction.

Run `python scripts/review_earnings_explanations_v8.py --check` to reproduce the pending sample. A later `--review` export requires a named human reviewer, timestamp, attestation and notes for each completed judgment.
