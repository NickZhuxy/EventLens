# Macro-event review

The macro-event extension's labels are in `data/macro/labels.draft.json`. Check each event against the cited next-meeting sentence and its publication date. These are draft calendar labels, not semantic-support labels. Review claim support through each macro run's `review_queue.json` and the `eventlens macro review` command. For the primary earnings workflow, use the [earnings review procedure](earnings_benchmark_v2.md#review-the-real-disclosures).

The instructions below apply to the separate earnings experiment.

---

# Label and semantic-evidence review

Current state: `data/labels.draft.json` contains six **AI-drafted** metric labels. No labels or observations have been reviewed by Nick. The real evaluation remains provisional.

## Review the labels

1. Read each primary source URL in `data/manifest.json`, then inspect its saved text. Check any normalization differences. One Autodesk appendix is incomplete, although its annual guidance table is present.
2. Verify the issuer, publication date, reporting quarter and **forecast** fiscal year. Salesforce FY2024 occurs in calendar 2023; its fiscal year ends January 31, 2024. Autodesk FY2026 guidance ends January 31, 2026. Do not compare different companies' FY labels as equivalent calendar intervals.
3. Check the exact metric, total versus segment scope, reported/GAAP/adjusted basis, currency, units, range endpoints and evidence. In Salesforce's table, choose the annual column, not the quarterly column. The label uses an explicit annual-guidance bullet as a second verification route.
4. Recompute each pair's midpoint change independently. Expected draft deltas: Adobe $125m; Salesforce $150m; Autodesk $90m.
5. Copy the draft file to `data/labels.reviewed.json`. Correct the copy and add a `corrections` list with source, field, old value, new value and reason. Retain the original draft.
6. Only after reviewing **all six records**, change top-level `status` to `human_reviewed`, set `reviewed_by` to your actual name and `reviewed_at` to an ISO timestamp. Partial review stays `ai_draft` with per-record notes. Preserve the source-hash map unless independently updating and relabeling the corpus.
7. Rerun with `eventlens evaluate --labels data/labels.reviewed.json --out reports/reviewed-run`. This changes label provenance, not the model's raw outputs.

## Review what the system actually asserted

`reports/offline-v2/review_queue.json` contains metrics and candidate explanations from real and synthetic runs. Start with the real cases. Check literal presence **and** semantic support. Ask whether the heading establishes the right horizon, whether numbers belong to the correct column, and whether an explanation actually links a driver to the revision instead of describing general performance.

For a real observation, copy its `observation_id` and record your judgment:

```sh
.venv/bin/eventlens review \
  --queue reports/offline-v2/review_queue.json \
  --observation OBSERVATION_ID \
  --reviewer 'Xiangyi (Nick) Zhu' \
  --decision supports \
  --note 'Checked the annual heading, revenue row, unit and values against the source.'
```

Use `reject` or `uncertain` when appropriate. This command appends a review with source hash and timestamp to SQLite and `data/reviews.jsonl`. It never rewrites a source, extraction or draft label. The name in this example is not proof that Nick has used the command.

Synthetic derivatives cannot be accepted as real-source observations by the review command. Their intended behavior is in each challenge record. They are engineering controls, not ground truth about management.

## Metrics after review

The evaluator reports label-based precision/recall and numerical errors separately from semantic-review results. This first version exports review records but does **not** aggregate them into a human semantic-support error rate. That field stays null. Compute and document that rate separately after adjudication, with its reviewed denominator; do not relabel automated screens as human review.

Record the exact label file, source hashes, model, prompts, command and output directory for any figure used in an application. Never call the current draft “manually annotated by Nick.”
