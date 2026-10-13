# EventLens macro-event specification

Current scope: a personal research agent that converts dated macro-event sources into concise, evidence-linked risk briefs. The user confirmed this direction on October 7, 2026. This supersedes the broad-news proposal and the earnings experiment as the project's primary purpose.

## User workflow

Select a date window, market scope, and information cutoff. Let one agent inspect the event calendar, search eligible sources, read supporting passages, and submit a brief. Python validates the draft and returns errors for correction. Save the accepted draft and complete trace for analyst review.

## Implemented first version

- Python 3.11+, a CLI, a provider-compatible HTTPS model adapter, and SQLite/JSON persistence.
- Five public Federal Reserve source documents; two historical FOMC briefing cases.
- Source-derived meeting dates, exact citations, separate publication/context/capture times.
- Three read-only tools: `list_events`, `search_sources`, and `read_source`.
- A bounded JSON-action controller with validation feedback and revision.
- Claim categories for historical/current facts, current market expectations, and conditional risk interpretations.
- Rule baseline, single-pass model path, agent path, and explicitly scripted controller fixtures.
- Append-only briefs, run traces, source identities, and analyst review records.

## Acceptance and evidence

The offline workflow must run from a clean installation. Future publications and late captures in strict mode must be inaccessible. A citation must refer to an exact interval actually supplied to the method. Invalid drafts must remain in the trace without becoming published briefs. Failures and budget exhaustion must be explicit.

The current saved evaluation checks calendar inclusion and mechanical validity against draft labels. Live model quality and semantic support are unmeasured. Automated checks do not replace semantic review. `ready_for_review` is not an analyst endorsement.

## Next research work

Run the same live model on the single-pass and agent paths, then review the results. Expand source types before claiming current consensus or historical market effects. Add event adapters and prospective or verified archival data. Measure usefulness and editing effort on unseen cases.

The project does not predict profitable trades, execute portfolio actions, or claim an approved course submission. The original earnings workflow remains a separate supporting experiment. See `docs/architecture.md` for the implemented contract.
