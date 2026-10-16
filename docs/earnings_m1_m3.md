# Expanded earnings corpus and document-diff baseline

Implementation and collection checkpoint: October 13, 2026. This checkpoint implements the corpus expansion and method D. It does not establish the full earnings-agent claims: labels, live B/C evaluation, held-out stress evaluation, and human explanation-support review remain pending.

This is the preserved M1/M3 checkpoint. The later [v2 execution report](earnings_benchmark_v2.md) adds the completed four-method live comparison and held-out synthetic tests. Human-reviewed accuracy remains pending there as well.

## Corpus and split

The [saved inventory](../reports/earnings-m1-m3-2026-10-13/corpus_review.json) contains 36 adjacent quarterly earnings pairs from 12 issuers: 12 development pairs and 24 held-out pairs. It references 52 source snapshots, including supplementary and duplicate-source captures that do not increase the event count.

The [issuer allocation](../configs/corpus_v2_split.json) was recorded before expansion or D implementation. Development issuers are Adobe, Intuit, Synopsys, and Box. Held-out issuers are Salesforce, Autodesk, Cadence, Zoom, Zscaler, Datadog, Okta, and HubSpot. Existing Adobe/Salesforce/Autodesk exposure is disclosed in the freeze. This is an issuer-separated convenience sample, not blinded external validation. Three pairs from each issuer are consecutive releases spanning the previous Q4 through Q3. Synopsys' acquisition changes consolidation scope; same-horizon eligibility does not imply numerical comparability.

Thirty-five pairs use SEC-hosted exhibits on both sides. The original Autodesk Q1–Q2 issuer-site pair is retained for exact reproduction of the pilot. Complete SEC copies of both Autodesk releases are also saved, but are not counted as another pair. The original six snapshots and three cases are preserved; their input metadata are archived in `data/pilot_v1/` (snapshot paths there refer to the original `data/` directory).

All 46 new captures cover every numbered reader line. [The audit](../data/capture_audit_v2.json) records URL, retrieval timestamp, raw-capture hash, normalized-text hash, and coverage. Direct HTTP requests returned 403, so the raw captures are complete web-reader responses, **not original HTML bytes**. Normalization is reproducible from those responses; the reader's own HTML conversion is external. No source values are generated during normalization. Publication dates use the prior conservative end-of-day New York policy, not verified historical byte availability.

## Natural hard cases

Exact spans and offsets are saved in the inventory. These are AI-collected observations awaiting Nick's review, not gold labels.

- Salesforce FY2024 Q2–Q3 changes only the lower revenue bound.
- Intuit FY2025 Q3 repeats its previous guidance growth range alongside new guidance. This is a restatement of prior guidance in prose, not an accounting restatement.
- Synopsys FY2025 Q2's annual table uses millions; Q3's headline uses billions. The Ansys acquisition also changes consolidation scope.
- Box's reported dollar range falls while its constant-currency discussion describes an increase. Different bases must not be mistaken for contradictory claims.
- Synopsys' May 29, 2025 8-K suspends guidance. This supplemental notice is not an earnings exhibit and is excluded from the 36 quarterly pairs.
- Adobe Q3–Q4 moves from FY2025 to FY2026 targets. This rollover is excluded from the 36 same-horizon pairs.

A switch in the reported currency itself has not been established. The corpus includes unit representation and currency-basis differences; these are distinct phenomena.

## Method D: sentence-level document diff

[Implementation](../src/eventlens/document_diff.py), [freeze](../configs/document_diff_freeze.json), and [tests](../tests/test_document_diff.py).

1. Split each release into prose sentences, headings, and table rows, retaining exact source offsets. Preserve decimal points.
2. Align normalized whitespace strings with `difflib.SequenceMatcher(autojunk=False)`.
3. Save changed revenue sentences with numeric or withdrawal text and their edit operations. Find annual guidance candidates using guidance keywords, the requested horizon, and up to 1,200 preceding characters of heading context.
4. Parse an unambiguous dollar range or point value. Unit headings can supply millions. Repeated identical guidance collapses to one candidate; competing ranges and ambiguous multi-column rows cause abstention.
5. Match the two candidates through the diff alignment. A moved sentence may match with digit-masked text similarity of at least 0.5. Retain equal guidance sentences to recognize maintained guidance.
6. Use the same literal-evidence validation, eligibility gates, and `Decimal` reconciliation as A/B/C. Save failed validation as well as successful output. D uses no model, labels, external retrieval, or issuer-specific exceptions.

D is independent of A's extractor. Its thresholds were developed on the original Adobe pair and synthetic fixtures, then frozen before any expanded held-out runs. A's extraction code was not changed. D's explanatory passages use the existing deterministic candidate collector; they do not establish investigation or causal support.

Known limits: sentence alignment is lexical; mixed quarterly/annual tables, multiple guidance columns, and some full-year heading forms remain unsupported. The common evidence screen also rejects some otherwise plausible candidates. Constant-currency text can trigger conservative abstention. These failures remain in the saved runs; there was no tuning after inspecting held-out results.

## Saved operational results

The [evaluation](../reports/earnings-m1-m3-2026-10-13/report.md) and [JSON summary](../reports/earnings-m1-m3-2026-10-13/summary.json) contain A and D on all 36 real pairs and nine original synthetic controls: 90 method/case runs. B/C have not been run live.

| Method | Split | Pairs | Numeric comparisons emitted | Abstentions | Model calls |
| --- | --- | ---: | ---: | ---: | ---: |
| A | Development | 12 | 5 | 7 | 0 |
| D | Development | 12 | 5 | 7 | 0 |
| A | Held out | 24 | 2 | 22 | 0 |
| D | Held out | 24 | 14 | 10 | 0 |

These are operational counts, **not accuracy**. Five D extractions on held-out inputs failed the shared semantic screen. Only the original three cases have draft numerical labels; none has been reviewed by Nick. The report explicitly shows labeled-case denominators. Missing labels never become negative examples or correct predictions. Review all labels before claiming revision precision/recall, direction accuracy, or numerical exact match. The nine synthetic controls are development controls, not held-out stress evidence.

## Offline reproduction

From the repository root, with Python 3.11 or later:

```sh
python scripts/prepare_earnings_corpus.py --check
python scripts/earnings_eval.py --replay reports/earnings-m1-m3-2026-10-13
python -m unittest discover -s tests -v
```

To create another append-only run bundle:

```sh
python scripts/earnings_eval.py --out reports/my-earnings-offline-run
```

The corpus check rebuilds exact snapshots and metadata from saved captures. Replay checks bundle/input/code hashes, regenerates all 90 A/D outputs, compares all evidence/conclusion fields, and reproduces the report from saved measured latency and label inputs. UUIDs and fresh execution latency are excluded from output equivalence. [Saved replay verification](../reports/earnings-m1-m3-2026-10-13/replay.json).

For direct D use:

```sh
python -m eventlens compare --case ADBE-FY2025-Q2-Q3 --method D
```

The [review inventory](../reports/earnings-m1-m3-2026-10-13/corpus_review.json) has blank label and reviewer fields, source URLs/hashes, and old/new source windows. Window selection is a review aid, not evidence that its numbers are the correct annual guidance. Nick must inspect the complete source, supply labels, and record reviewer/time before a label can count as ground truth.

## Validation and next gate

[Saved validation](../reports/earnings-m1-m3-validation-2026-10-13/validation.json): 140 tests pass in a fresh installed environment; service smoke and recorded macro replay pass. The macro replay uses `--allow-earnings-changes`, which permits only explicitly named earnings modules to differ and still locks shared/model/macro code hashes. No macro results or recorded model responses were replaced. Local `.venv` contained numbered duplicate package files and timed-out reads; the fresh installation avoids that environmental problem. CI now includes the corpus and earnings replay checks; these local changes have not been pushed, so new remote CI is not claimed.

The next evidence gate is label review (M2), followed by a fixed-model cost estimate and explicit budget approval before M4. No paid model run, résumé edit, push, or section 6 decision occurred in this checkpoint.
