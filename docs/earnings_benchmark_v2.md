# Earnings investigation v2

This checkpoint extends the October 13 M1/M3 corpus and frozen baselines. It adds a human label-review page, a two-citation conflict output, corpus-wide stress controls, a cost-limited request journal, and model-response replay. Paid results and human-reviewed accuracy are separate stages.

## Completed execution

The [saved analysis](../reports/earnings-v2-analysis-2026-10-13/analysis.md) covers all 440 method/case runs and 342 complete provider requests. The [offline replay](../reports/earnings-v2-2026-10-13/replay.json) reproduces every request, evidence item, result and the frozen results table. Conservative token cost is USD 1.3671111 against the approved USD 8 cap; this is not an invoice.

Held-out numerical output coverage is A 2/24, B 4/24, C 4/24, and D 14/24. These counts do not establish correctness. For the 24 synthetic contradiction controls, two-citation flags are A 24, B 2, C 1, and D 17. C's [successful Okta trace](../reports/earnings-v2-2026-10-13/runs/OKTA-FY2025-Q2-Q3~v2-contradictory_commentary_C.json) retrieves both invented statements and records their synthetic origin. It is a bounded demonstration, not natural-conflict accuracy.

After controller failures are excluded from success, valid missing-evidence abstentions are A/D 24/24, B 9/24, and C 5/24. Stale-pair guards reject all 24 variants per method before any model access. All 36 natural labels and all semantic judgments remain pending. [Protocol findings](earnings_protocol_findings.md) describe the dominant development failures. [Local validation](../reports/earnings-v2-validation-2026-10-13/paid-validation.json) records 159 passing tests and reproduction checks; no new remote CI run is claimed.

## Review the real disclosures

Build the self-contained page:

```sh
python3 scripts/earnings_review.py --build /Users/nickzhu/Desktop/Library/AiHTMLs/Projects/EventLens/disclosure-review.html
```

The page embeds all source text for 36 real pairs, source hashes, candidate guidance windows, and the original three AI drafts. The other 33 labels start blank. It uses no external scripts or network requests. Browser storage keeps edits locally; exporting JSON creates a portable backup. Browser storage can be cleared by the browser, so export before closing.

1. Select a pair and check both source windows. Choose “Full saved release” when the window is incomplete.
2. Set each metric's status, currency, scale, bounds, and basis. Select exact text in the source and use the quotation buttons to copy the revenue statement and its contiguous horizon context. For a point estimate, enter equal bounds.
3. Choose the direction and record management explanations as exact quotations. A conflict requires two distinct opposing quotations. Distinguish reported versus constant-currency guidance and acquisition-scope changes.
4. Enter your name, review notes, and the personal-review attestation. Mark only the current pair reviewed. Editing any label field reopens that pair.
5. Export the review JSON. Validate it before using it for scoring:

   ```sh
   python3 scripts/earnings_review.py --validate /absolute/path/eventlens-label-review.json
   ```

Partial review is allowed. Only records with explicit attestation, reviewer identity, timestamp, valid source hashes, and consistent labels enter accuracy metrics. Python calculates normalized bounds and deltas from the reviewed values. The original drafts are preserved. The page never labels synthetic disclosures as management statements.

The method-output semantic review queue is a separate `review_queue.json` in each benchmark bundle. A label for a real disclosure does not automatically approve every explanation a model emits. Human explanation-support rates remain null until those observations are adjudicated.

After execution finishes, prepare a reproducible review sample:

```sh
python3 scripts/review_earnings_explanations.py reports/earnings-v2-2026-10-13 \
  --out reports/earnings-v2-analysis-2026-10-13/semantic-review.template.json
```

The sample uses the first eight SHA-256 candidate identities per method and kind among emitted natural held-out explanations and conflicts, deduplicating identical candidates. The selection rule is an operational review aid defined after execution, not a preregistered experiment. It does not sample failures with no output or synthetic controls. Inspect each quoted passage in its full source and use the questions embedded in the template.

Copy the template to a separate JSON file. For each reviewed entry, set `decision` to `supported`, `unsupported`, or `uncertain`, enter `reviewed_by`, an ISO timestamp with timezone in `reviewed_at`, and `notes`, and set `human_attestation` to `true`. Leave unreviewed entries `pending`. Preserve every candidate and its evidence.

```sh
python3 scripts/review_earnings_explanations.py reports/earnings-v2-2026-10-13 \
  --review /absolute/path/semantic-review.json --out reports/my-semantic-scores.json
```

The scorer rejects changed evidence, dropped candidates, and missing reviewer provenance. It reports support among reviewed sampled candidates, including uncertain judgments in the denominator, alongside reviewed and pending counts. These are conditional support rates for emitted candidates, not overall detection accuracy. Keep the review export with the scored artifact; its hash binds the scores to the judgments. The original frozen benchmark retains its null semantic-rate fields; this separate scoring artifact holds later human results.

## Fixed comparison

- A: unchanged deterministic rules.
- B: one model request with both complete saved disclosures.
- C: the same model and extraction instructions, with at most eight model calls and seven pair-scoped retrieval calls.
- D: unchanged sentence-level document diff.

All four use the original metric evidence screen and `Decimal` arithmetic. The original validator is deliberately conservative; it can reject valid multi-column tables, long horizon passages, or units expressed outside the quoted row. We preserve those failures rather than tune on held-out model results. The new `investigation.py` leaves the frozen M1/M3 and macro code paths unchanged.

B/C return metrics, explanation quotations, optional apparent conflicts, and optional comparability warnings. Each apparent conflict requires two distinct literal statements from the allowed pair. For C, both must be in retrieved context. Python saves their URL, source hash, offsets, and quotation. Literal validation does not establish semantic contradiction; natural conflicts remain review candidates. Acquisition scope, forecast year, or currency basis differences should produce a comparability warning when supported, rather than an invented conflict.

## Population and stress controls

The complete plan is 440 method/case runs:

| Population | Cases | Methods | Runs |
| --- | ---: | ---: | ---: |
| Real quarterly pairs: 12 development, 24 held out | 36 | 4 | 144 |
| Held-out synthetic controls: three per real pair | 72 | 4 | 288 |
| Natural supplements: withdrawal and fiscal rollover | 2 | 4 | 8 |

The supplements use development issuers and do not increase the quarterly-pair or held-out denominators. Unit and consolidation-scope differences in the real corpus need reviewed labels before their correctness can be measured.

The stale control substitutes the older release for the newer release. Eligibility fails before model access. The contradictory-commentary control appends two explicitly synthetic opposite statements about the same guidance, driver, horizon, and basis; scoring checks both the conflict flag and the two expected citations.

The control named `missing_table` masks **all numeric tokens throughout the new disclosure**, including duplicated guidance prose, actuals, and year headings. This prevents hidden copies of the same forecast from leaking into the control. It is a broad missing-numerical-disclosure test, not an isolated table-parser ablation. Every removed span and parent/derived hash is retained. A narrower table-removal study requires adjudicated source spans and is not claimed here.

## Budget and resumable runs

The fixed model is `deepseek-flash`, with `reasoning_effort=low`, 3,200 output tokens per request, a 180,000-character context limit, and no transport retries. The peak-price planning estimate is USD 5.6321. Nick approved the USD 8 cap on October 13; the [approval record](../reports/earnings-preflight-2026-10-13/approval.json) binds it to the frozen configuration. The planning status inside that immutable configuration is superseded by the separate approval record. These are estimates, not invoices. See [the saved estimate](../reports/earnings-preflight-2026-10-13/cost_estimate.json) and the [provider's pricing page](https://api-docs.deepseek.com/quick_start/pricing/), checked October 13, 2026. All input is priced as cache miss; discounts are not needed for the guard.

Prepare and run the deterministic part without any provider access:

```sh
python3 scripts/earnings_benchmark.py --out reports/earnings-v2-2026-10-13
```

The bundle freezes sources, cases, configuration, and code hashes. The live command requires an explicit approval JSON with `status: approved`, the exact `model`, the `config_hash` of the bundle's `config.json`, and `cap_usd`. Create that record only from Nick's actual approval. General permission for paid work does not manufacture an approved budget record.

After budget approval:

```sh
python3 scripts/earnings_benchmark.py \
  --out reports/earnings-v2-2026-10-13 --resume --live \
  --approval /absolute/path/approval.json --env-file .env
```

The optional `.env` loader accepts only the named EventLens/DeepSeek settings and never executes shell text. Credentials remain in process memory; they are excluded from saved requests. Each journal entry saves the messages, model, provider settings, output limit, raw response, token usage, and cost reservation.

Before a request, the journal reserves a conservative UTF-8-byte input bound plus the output token cap. Successful responses release unused reservation based on reported usage. Failed or uncertain requests retain the reservation and stop the run. Resuming reuses exactly matching saved responses, including partial controller traces; it never automatically repays an uncertain request. A budget denial leaves the method/case pending rather than counting it as a scientific abstention.

Replay has no adapter with network access:

```sh
python3 scripts/earnings_benchmark.py --replay reports/earnings-v2-2026-10-13
```

Replay checks bundle and code hashes, regenerates every request, consumes the recorded responses, compares evidence/decisions/calculations, and reproduces the table. Recorded latency is retained for aggregation; new wall-clock replay latency is not substituted.

Preserve the published execution bundle when labels arrive. Copy it to a new scoring directory, then add the explicit review export there:

```sh
python3 -c "import shutil; shutil.copytree('reports/earnings-v2-2026-10-13', 'reports/earnings-v2-reviewed-01')"
python3 scripts/earnings_benchmark.py --out reports/earnings-v2-reviewed-01 \
  --resume --labels /absolute/path/eventlens-label-review.json
python3 scripts/earnings_benchmark.py --replay reports/earnings-v2-reviewed-01
```

The importer validates labels and leaves raw model outputs unchanged. These commands do not use live mode. Each later label revision needs another scoring copy so prior labels/results and their analysis hashes remain reproducible. The runner permits one initial label import per copy.

## Measurement boundaries

- Revision detection and direction accuracy use only human-reviewed real cases.
- Numerical exact match requires all four normalized endpoints and the midpoint delta; abstained eligible comparisons remain misses in its denominator.
- Direction uses raised/lowered/maintained/withdrawn/mixed-range/not-comparable. A numerical abstention maps to not-comparable; a missed valid revision remains wrong.
- Stress-status and expected-citation checks use construction-known synthetic outcomes, independently of real-label review.
- Use the separate execution analysis for stress decisions without controller failures. The frozen report's raw expected-status column also counts failures that end in `insufficient_evidence`; those matches alone are not correct abstentions. Stale-pair rejection is the intended eligibility check and is counted as a valid decision.
- The contradiction template's vocabulary appears in C's search hint and A/D's lexical checker. These controls test the known construction and citation path; they do not establish generalization to unseen natural contradictions.
- The absence-control fabrication metric counts an extracted provided metric attributed to a missing/current source, including candidates rejected by the metric screen. Malformed responses and earlier controller rejections can prevent candidate extraction. Zero counted candidates does not establish zero fabrication across all raw model text or natural explanations.
- Costs, calls, token usage, coverage, errors, and latency are operational measurements. They do not become accuracy claims.
- Historical cutoff replay does not remove model-training exposure. No investment-return or leakage-free-alpha result is claimed.
