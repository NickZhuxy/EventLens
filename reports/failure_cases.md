# Failures and challenge behavior

Primary outputs: `offline-v2/`. All label-dependent accuracy claims are provisional. Original outputs are retained.

| Case | Observed behavior | Interpretation |
| --- | --- | --- |
| Salesforce FY2024 Q1→Q2, real | A abstains despite available annual guidance | Two missed metric records; the table mixes quarterly and annual columns. Draft expected midpoint increase is $150m. This is a real baseline failure. |
| Adobe missing annual table row, synthetic | Abstains | It does not substitute the still-present quarterly forecast. |
| Adobe mismatched lower/upper scales, synthetic | Abstains | One bound says million and the other billion. The range parser refuses ambiguity. |
| Adobe unknown units, synthetic | Abstains | It does not invent a conversion for widgets. |
| Adobe FY2026 heading substituted for FY2025, synthetic | Abstains | It does not compare the requested horizon against a different year. |
| Adobe stale release substituted as current, synthetic | Abstains before extraction | Chronological/source-order gate rejects the pair. |
| Adobe cutoff moved before new release, synthetic | Abstains before extraction | Both read tools enforce the same cutoff; no future context is available. |
| Adobe opposing explanations, synthetic | Flags conflict while retaining numerical change | The assertions are invented test inputs. A narrow lexical detector recognizes an explicit demand contradiction. |
| Adobe two annual ranges, synthetic | Flags conflicting guidance | It does not choose a convenient range silently. |
| Adobe appended prompt injection, synthetic | Original numerical result preserved under A | Rule execution does not follow source instructions. No live-model robustness conclusion follows. |

## Development defect retained in history

The initial end-to-end contradiction demo failed because candidate retrieval matched `driv` but missed `drove` and `cause`. The isolated contradiction function test passed, showing why an end-to-end test was necessary. The development fixture drove a small fix and a new pipeline regression test. `configs/freeze.json` records the amendment; `reports/runs/c6eb90ff-3160-4e67-b518-f57d3d45eab1.json` retains the failed output.

`reports/first_frozen_baseline.json` preserves the original real-case run before that repair. `offline-v1/` is retained but superseded: its synthetic emitted-calculation count was incorrectly zero and one conflict reason was generic. `offline-v2/` corrects those reporting defects without changing the favorable/unfavorable real-case outcomes. No run was deleted to improve the reported result.

## Unmeasured failures

Live B/C accuracy, malformed live provider responses, actual model behavior under injection, tool-selection quality, and token/latency tradeoffs remain unmeasured. Mock tests exercise error paths without claiming real model performance. The evidence screen is conservative but not an entailment oracle; human semantic-support errors remain null until adjudication.
