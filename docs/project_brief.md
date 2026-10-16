# EventLens project brief

EventLens investigates annual revenue-guidance changes across earnings disclosures. It compares a retrieval agent with rules, a single-pass language model, and a document-diff baseline. The primary question is whether the agent can reconcile changes and investigate explanations using literal source evidence. Human-reviewed correctness remains unmeasured.

The [earnings benchmark](earnings_benchmark_v2.md) contains 36 real disclosure pairs across 12 issuers and 440 runs including synthetic controls. Full requests and responses support exact offline replay. See the [execution analysis](../reports/earnings-v2-analysis-2026-10-13/analysis.md) for coverage, failures, costs, and limitations.

EventLens is a personal research implementation. It uses public sources and includes no employer code or documents.

## Macro-event extension

The retained secondary workflow produces cited macro-event risk briefs: upcoming events, relevant expectations, possible risk channels, and missing evidence. The sections below describe its original experiment.

### Macro methods

- Rules: extract the next FOMC meeting from eligible minutes and quote the latest eligible policy statement.
- Single pass: give the complete eligible corpus and calendar to one LLM call.
- Agent: let one LLM choose read-only tools and revise a draft in response to validation errors.

The two model methods share a model, corpus, case, cutoff, output schema, and validator. Their context and compute budgets differ. That difference must be reported when comparing results.

### Original macro experiment

The corpus contains five public Federal Reserve documents. July 2025 is the development case; September 2025 is a temporal check. Both have source-supported upcoming meeting dates. The second case was inspected during development and is not a blinded holdout.

The original rule baseline and scripted controller path run offline. A later [saved live run](../reports/deepseek-live-2026-10-08/brief.md) used 11 public source versions, five model calls, and three tool calls. Its rejected first draft and accepted repair replay exactly. This is one bounded execution trace, not a broad model-reliability evaluation.

The source set has no dedicated current-consensus data and no independently verified market-reaction series. These gaps appear in the briefs. Publication-time replay uses documents captured later, so it is not a contemporaneous archive.

### Macro evaluation

The saved report measures calendar inclusion, mechanical validity, length, and execution statistics where observed. Calendar labels are AI drafts awaiting review. Semantic support accuracy and analyst editing time remain unmeasured. No retrieval improvement, profitable signal, or trading impact is established.

Read [the saved report](../reports/macro-v1/report.md), [architecture](architecture.md), and [source provenance](macro_data_provenance.md). The primary [earnings experiment](earnings_experiment.md) retains its earlier data and findings.
