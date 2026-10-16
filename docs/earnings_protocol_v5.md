# V5: exact table references and explanation retrieval

V5 addresses the two remaining problems in the [v4 development run](../reports/earnings-v4-analysis-2026-10-15/analysis.md): literal quotation/annual-column failures on Synopsys and failure to retrieve both synthetic conflict statements on three controls. **The approved pilot is complete:** 32 B/C runs, 64 requests and USD 0.1967478 conservative token cost. Every request and result replays exactly. [Full analysis](../reports/earnings-v5-analysis-2026-10-15/analysis.md).

Both methods produced numerical comparisons on all four selected real development pairs, including Synopsys; both passed all four broad missing-evidence controls and four stale guards. C retrieved both injected statements on all four contradiction controls, but neither method completed a valid conflict flag: the model put quote text into fields where the validator required evidence IDs. The unchanged v5 failures are preserved. [V6](earnings_protocol_v6.md) tests a separate interface correction offline; a further paid check needs new approval.

## Table evidence

[The evidence module](../src/eventlens/evidence_v5.py) constructs source-specific metric and citation IDs. The model selects IDs rather than rewriting numeric rows, whitespace or quotations. Python resolves each selected ID to the immutable source, verifies visibility and the source hash, and uses the existing Decimal comparison. An invented ID or an ID not returned by a successful retrieval is rejected. Quotes, offsets, URLs and source hashes remain in accepted output records.

Simple rows and prose still use the existing literal metric validator. A separate parser handles a bounded mixed quarterly/annual pipe-table layout. It requires an explicit full-fiscal-year forecast heading, period groups, matching Low/High labels, matching dollar-value pairs, a unit heading and the requested fiscal-year date. It maps the annual group's two cells by group order. It also records exact source spans for the annual header, date, unit, row, low/high labels, currency cells and selected numeric cells. This is a structural proof for this layout; it does not remove the old validator's quarterly guard or excuse nonliteral quotes.

Missing or ambiguous headers, unmatched column counts, contradictory candidate ranges, reversed bounds, absent units, unsupported currency qualifiers and unrecognized layouts produce no selectable metric. The parser has no issuer-name exceptions. It is not a general HTML table parser: the corpus consists of normalized text, and lost table structure can still require abstention.

## Explanation retrieval

`review_explanations` ranks short literal guidance/driver statements across the entire allowed disclosure. It returns up to twelve distinct statements with evidence IDs. This avoids spending the initial retrieval budget on overlapping numerical windows alone. The lexical ranking covers causal/driver language and can retrieve positive and negative assertions, including statements near the end of a document. It does not label statements as contradictions.

C must complete `inspect_guidance` and `review_explanations` for both disclosures before finishing. Those four actions count toward the existing seven-retrieval budget. The controller reserves enough remaining actions for outstanding reviews; optional searches cannot consume that reserve. Further source reads/searches remain available. Native batches retain atomic publication: a rejected batch exposes no partial evidence.

The model must choose two distinct visible statements for an apparent conflict and explain their common proposition, period, basis and scope. Different periods, reported versus constant-currency values, segment versus total revenue, or different consolidation scopes are not automatically conflicts. Literal references establish source identity, not semantic contradiction or causality. Human review remains necessary.

## Baseline and measurement boundary

B remains one model call. It receives the full allowed disclosures plus the **same** four evidence catalogs that C can retrieve. Both methods select metric/citation IDs using the same validator. B has no retrieval calls. C can investigate further within its stated budget.

This is a **hybrid parser-and-model experiment**, not merely a new prompt for the earlier free-form extraction task. Deterministic candidate availability must be reported separately from live model selections. Any numerical coverage gain can come from the parser; it cannot be attributed solely to model reasoning or the agent loop. A/D, v2–v4 code, saved failures and original held-out results remain frozen. V5 is available through its versioned runner; it has not replaced the default CLI or established a new headline benchmark.

## Saved offline evidence

- **211 tests pass**, including 23 new v5 tests. [Test log](../reports/earnings-v5-validation-2026-10-15/tests.log).
- The deterministic catalog supplies one candidate for each source in the four selected real pairs, including the annual columns of both Synopsys releases. This is parser coverage, not human-reviewed accuracy.
- Whole-source statement retrieval returns both expected injected statements for all four existing synthetic contradiction controls. The subsequent live run also retrieved both in all four C controls, but its final conflict references failed validation.
- Tests cover mixed-period column order, Unicode spaces, currency/unit and period mismatches, ambiguous ranges, foreign/unseen/tampered IDs, bounded atomic publication, required review coverage, baseline parity and a table-row-only deletion fixture. The latter is not a completed live table-only ablation.
- **32 explicitly scripted B/C traces** replay exactly, with zero network or paid calls. The scripted fixture uses construction-known expected statements when selecting a conflict. It is not an LLM performance result. [Offline verification](../reports/earnings-v5-validation-2026-10-15/scripted/verification.json).

Reproduce from the repository root:

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
python scripts/verify_earnings_protocol_v5.py reports/earnings-v5-preflight-2026-10-15 \
  --out reports/earnings-v5-validation-2026-10-15/scripted --check
```

## Frozen estimate and approved execution

The [preflight estimate](../reports/earnings-v5-preflight-2026-10-15/estimate.json) contains the same four exposed development pairs plus four stale, four broad numerical-mask and four construction-known contradiction controls. Both B and C run, for **32 method/case runs**. Stale variants reject before model access. The maximum is **108 model requests**. All initial full-document B requests fit the unchanged 128,000-byte limit; the controller checks later context growth before each request. C still permits eight model calls, seven retrievals and two validation repairs. Per-call output remains 6,000 tokens.

| Cost measure | USD | Meaning |
| --- | ---: | --- |
| Planning scenario | 0.5112 | Per eligible B case: one call with 32,000 input / 3,000 output tokens; per C case: seven calls with 10,000 / 1,000 tokens each |
| Conservative full-budget estimate | 5.0575104 | Every allowed request at the full input-byte/output limits, plus input overhead |
| Approved hard cap | 5.50 | Journal reserves before each call and stops before exceeding the cap |
| Prior v3 + v4 cost | 0.3410172 | Recorded conservative token cost |
| Prior cost + proposed v5 cap | 5.8410172 | Remains below the prior USD 6 allocation |
| V5 recorded token cost | 0.1967478 | 64 complete requests, zero uncertain charges |
| V3 + v4 + v5 recorded token cost | 0.5377650 | All three approved pilots completed |

Prices use DeepSeek Flash peak cache-miss rates, USD 0.30 per million input tokens and USD 1.20 per million output tokens, checked on October 15 against the [official pricing page](https://api-docs.deepseek.com/quick_start/pricing/). Cache and off-peak discounts are ignored. These are estimates, not invoices.

Nick approved “Approve up to $5.50 USD.” The [approval](../reports/earnings-v5-preflight-2026-10-15/approval.json) binds this bundle's frozen code and inputs. Preflight fields that say `pending` or `not_started` preserve their original preparation state; the approval, summary and analysis record the later execution. Reproduce the completed pilot without network access:

```sh
python scripts/analyze_earnings_protocol_v5.py reports/earnings-v5-preflight-2026-10-15 \
  --out reports/earnings-v5-analysis-2026-10-15 --check
```

All attempts, failures and reservations are retained. The analysis compares every selected case with matching v3/v4 inputs and reports deterministic candidate availability separately. Numerical output coverage is not accuracy. Free-form model prose also needs review: a [saved BOX example](../reports/earnings-v5-analysis-2026-10-15/prose-arithmetic-note.json) contradicts the deterministic upper-bound delta. The 36 real labels, semantic explanation review, natural-conflict cases, a full table-only stress experiment and fresh unseen validation remain outstanding. No further paid run is authorized by the completed v5 approval.
