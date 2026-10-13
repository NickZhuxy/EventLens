# Macro-event agent architecture

EventLens uses one model-controlled research loop over source versions fixed for each job. The model chooses tools and writes a structured draft. Python defines the tools, filters the corpus, validates the draft, and stores the result. A FastAPI service and a separate worker make this engine available over HTTP. The service collects new public sources and accepts analyst imports; it does not require a separate planner model or vector database.

## Entry point and state

The deployed path starts at `service.api.create_app`. `POST /v1/briefs` records the case, source IDs, method, and configuration in `service.store.Database`. A worker claims the job in a SQLite transaction and calls `macro.agent.run_brief`. The result, rendered brief, and review queue are committed together. HTTP requests do not execute the model in the API process. See [deployment operations](deployment.md) for the job state machine, leases, authentication, and recovery.

`eventlens macro brief` reaches `macro.cli.execute`, which loads `data/macro/manifest.json`, the selected case, and `configs/macro.json`. `macro.agent.run_brief` creates the eligible corpus and run record. `_investigate` owns the model loop.

The state consists of:

- The fixed request: window, selected regional and global markets, information cutoff, and question.
- Eligible source metadata and the source-derived calendar.
- Model messages, tool results, and remaining call budgets.
- The exact source intervals returned to the method and calendar events it has seen.
- Draft validation results, errors, usage, timing, and the accepted draft, if any.

The model receives only eligible source metadata. An excluded document does not enter a model message. The full run record separately retains corpus hashes and excluded IDs so that a reviewer can audit the boundary.

## One model turn

The adapter requests a JSON object using `LiveAdapter` in `llm.py`. The supplied environment selects DeepSeek Flash. For `https://api.deepseek.com`, the adapter sends `model`, `messages`, `max_tokens`, `response_format`, and explicit thinking controls to `/chat/completions`. Low reasoning effort is the default. Other endpoints retain the existing `max_completion_tokens` and `store: false` fields. `ProviderSettings` validates the endpoint and restricts provider-specific fallback keys to their corresponding official hosts.

The queue saves the nonsecret provider settings with each request. Successful model responses also record the actual endpoint, reasoning effort, and HTTP attempt counts. A changed worker endpoint stops a queued model job before any provider call. Credentials stay in the worker environment.

The controller reads the action from the response's `content` field. DeepSeek can also return `reasoning_content`; the trace preserves that response field, but the controller does not execute it or use it as evidence. This JSON action protocol does not send the provider's native `tools` parameter, so previous reasoning fields do not need to be sent again. See [DeepSeek's multi-turn rules](https://api-docs.deepseek.com/guides/thinking_mode/).

The action protocol has two branches:

```json
{
  "action": "tool",
  "name": "search_sources",
  "arguments": {"query": "inflation employment policy risks"},
  "reason": "Find the policy discussion that the brief still needs."
}
```

```json
{
  "action": "finish",
  "brief": {"items": [], "omissions": []}
}
```

In broad-scope mode the model may return no selected events after inspecting the universe. Narrow historical evaluation still requires explicit inclusion or omission of each event. It yields `insufficient_evidence`, not a claim that no market events exist.

A tool action is validated and dispatched to `ResearchTools.execute`. Its literal result becomes the next model input. An invalid tool request returns an error that the model can use to recover. Unknown tools cannot execute code, read arbitrary files, or access the network.

A finish action is passed to `validate_brief`. A valid draft ends the loop. An invalid draft is retained in the trace, and its errors are returned for revision. Invalid drafts never become the published `brief` field. Malformed protocol output, transport failure, context exhaustion, or exhausted call budgets ends the run with an explicit failure.

The saved `reason` is a short action rationale requested by the protocol. The trace records observable actions and outputs.

## Tools

| Tool | Arguments | Result |
| --- | --- | --- |
| `list_events` | Empty object | Calendar records and literal date evidence |
| `search_sources` | `query`, 1–300 characters; optional `event_id` and `kind` | Up to five literal paragraphs, scores, offsets, and source metadata |
| `read_source` | `source_id`, integer `start`, integer `end` | One exact span, at most 6,000 characters |

Search ranks word overlap, then the source's document date. It is not semantic retrieval, and a high score does not establish relevance. The model can read surrounding text when a result is incomplete.

Sources cannot change the run's scope. Read tools accept no URLs or filesystem paths. Network collection is separate from agent execution. `service.ingestion.refresh_fed` reads the monetary-policy RSS feed, follows supported Fed article links, and saves immutable source versions. A job fixes the available versions before the model runs.

## Records

**Source.** `MacroSource` retains identity, title, publisher, URL, publication time, availability time, capture time, context date, document kind, markets, topics, text, and SHA-256. The manifest also retains web-reader captures and release-date evidence hashes. `load_sources` checks paths and hashes.

**Event.** `catalog.py` defines 41 entries across regional and global markets. `schedules.py` decodes sourced occurrences, including tentative dates and windows. Undated entries stay on the watchlist. `providers.py` reads ECB, USDA, CFTC, NBS, NY Fed, and BLS schedules with per-provider failure isolation. The FOMC adapter extracts the next meeting's start and end dates from the explicit next-meeting sentence in eligible minutes. The event record includes its ID, name, market, category, date precision, timezone, and exact date evidence. It does not infer a release hour or derive dates from a meeting's usual frequency. Conflicting extracted date ranges require calendar review.

**Claim.** Each draft item contains an event ID, claims, and gaps. A claim has `kind`, `statement`, `context`, `channel`, and `evidence`. Kinds are `fact`, `expectation`, `risk`, `historical_impact`, and `analyst_view`. The last two require dedicated source types. Context is `current` or `historical`. Risk channels are policy, volatility, liquidity, and credit; other claim types have a null channel.

**Evidence.** Each citation carries `source_id`, `start`, `end`, and `quote`. Python checks that the quote equals the specified span and that the span was actually supplied to the method. A quote found elsewhere in the source is insufficient if that interval was never returned.

**Run and review.** The service commits `run`, `brief_markdown`, `calendar_csv`, and `review_queue` as one job result. Its request client downloads `brief.md`, `run.json`, and `review_queue.json`, plus the job record. The CSV keeps the full candidate universe and date uncertainty. Runs include model messages and responses, configuration, code and source hashes, actions, validation feedback, and measured usage when available. Reviews append without changing raw results. SQLite also stores the durable queue and source captures; retrieval operates over the selected text.

## Date semantics

The June meeting occurred on June 17–18, 2025, but its minutes were released on July 9. The minutes cannot be used before July 9, even though they discuss June conditions.

- `publication` requires publication and availability times at or before the cutoff.
- `snapshot` additionally requires the stored capture to have existed by the cutoff.
- `document_date` identifies the conditions discussed. It is separate from publication and capture dates.
- Current context older than `freshness_days` is rejected. Explicit historical context can remain available.

The 2025 documents were captured in 2026. Publication mode is a retrospective reconstruction. It is not evidence of a contemporaneous archive or protection against every possible page revision. Snapshot mode correctly excludes these captures from both 2025 cases.

## What validation does and does not establish

The validator checks schema, event coverage, duplicate records, exact evidence intervals, access boundaries, context age, narrative length, and a conservative check that numerals in facts appear in their cited evidence. It rejects numerical risk forecasts. An expectation claim requires a dedicated, current `market_expectations` source.

These are mechanical checks. They do not prove that a paraphrase follows from its quote, that a risk channel is economically meaningful, or that a directional claim written without digits is acceptable. Every claim enters a semantic review queue. `ready_for_review` means the mechanical checks passed; it does not mean the analyst accepted the brief.

## Methods and evaluation

`rules` selects up to eight calendar entries and extracts their date evidence in broad-scope mode. The narrow historical evaluation retains the FOMC policy-sentence baseline. It deliberately supplies no market consensus or risk interpretation.

`single` supplies the complete eligible corpus and calendar in one model call. `agent` starts with metadata, then chooses tool calls. Both use the same model, case, corpus, cutoff, claim schema, and final validator. They differ in context and inference budget, so their comparison is not compute matched.

The service default allows 20 model calls, 18 tool calls, 6,000 output tokens per call, and 160,000 input characters per call. Maximum configured output across successful responses is therefore 120,000 tokens per case; actual provider usage is recorded when supplied. Input characters are not a token estimate. The provider socket timeout is 30 seconds per attempt, with at most two retries for transient errors. Transport attempts are recorded in successful responses; lost responses can incur usage that the client cannot measure. This is an execution budget, not a guaranteed dollar-cost cap.

Calendar labels are AI drafts. The report measures event precision/recall against those labels, mechanical validation, output length, calls, tokens, and latency where observed. Semantic support accuracy and analyst editing time remain null until reviewed data exists. The two related cases do not justify generalization claims.

## Source and research contracts

The calendar catalog, collector registry, structured imports, research claim types, and CSV schema are described in [the global workflow](global-workflow.md). New providers must preserve cutoff semantics and retain captures. Source pages without known publication timestamps use their first observation, never an inferred earlier publication time.

The independent earnings-guidance experiment remains in the original root modules. The macro workflow reuses its HTTP adapter, strict JSON parser, hashing, timestamps, and SQLite store. Its fiscal-period and arithmetic rules do not govern macro-event claims.
