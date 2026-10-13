# EventLens project brief

EventLens investigates whether a tool-using LLM can produce more accurate, better-supported macro-event briefs than a single-pass LLM. The intended user is an analyst supporting a quantitative investment team who needs a concise account of upcoming events, relevant expectations, possible risk channels, and missing evidence.

The problem comes from Nick's Jinde macro-event workflow: maintaining calendars, gathering context, and producing short warnings for the trading team. Nick confirmed that his basic information-organizing agent supported that workflow. EventLens is a new personal implementation; original model/framework details are unconfirmed and no employer code or documents are included.

## Methods

- Rules: extract the next FOMC meeting from eligible minutes and quote the latest eligible policy statement.
- Single pass: give the complete eligible corpus and calendar to one LLM call.
- Agent: let one LLM choose read-only tools and revise a draft in response to validation errors.

The two model methods share a model, corpus, case, cutoff, output schema, and validator. Their context and compute budgets differ. That difference must be reported when comparing results.

## Implemented experiment

The corpus contains five public Federal Reserve documents. July 2025 is the development case; September 2025 is a temporal check. Both have source-supported upcoming meeting dates. The second case was inspected during development and is not a blinded holdout.

The rule baseline and scripted controller path run offline. Model methods accept configurable live access but have not been evaluated with a live provider. The repair fixture demonstrates a rejected citation and a later valid draft; it is not evidence that an LLM will reliably repair itself.

The source set has no dedicated current-consensus data and no independently verified market-reaction series. These gaps appear in the briefs. Publication-time replay uses documents captured later, so it is not a contemporaneous archive.

## Evaluation

The saved report measures calendar inclusion, mechanical validity, length, and execution statistics where observed. Calendar labels are AI drafts awaiting review. Semantic support accuracy and analyst editing time remain unmeasured. No retrieval improvement, profitable signal, or trading impact is established.

Read [the saved report](../reports/macro-v1/report.md), [architecture](architecture.md), and [source provenance](macro_data_provenance.md). The separate [earnings experiment](earnings_experiment.md) retains its earlier data and findings.
