# Development pilot: native tool calls and validation feedback

This version addresses the operational failures recorded in [v2](earnings_protocol_findings.md). The approved pilot completed on October 15: **32 runs, 94 model requests, and USD 0.2376024 conservative token cost**. All requests and results replay exactly. The [analysis](../reports/earnings-v3-analysis-2026-10-15/analysis.md) reports both progress and failures. C completed three of four selected real development cases without terminal errors and produced two numerical outputs, but passed zero of four synthetic two-citation conflict checks. These are operational counts, not reviewed accuracy or an agent advantage.

## Implementation

The new [controller](../src/eventlens/protocol_v3.py) uses DeepSeek native function calls with strict schemas, rather than parsing tool actions from assistant prose. It still validates function arguments locally. It never executes the prefix of a malformed response or treats model-generated tool output as retrieved evidence.

B and C use the same `deepseek-flash` model, non-thinking mode, 6,000-token output limit, and 128,000-byte full-request limit. B receives both complete saved disclosures in one call. C begins with source metadata and has at most eight model calls, seven read-only retrieval calls, and two validation repairs within those eight calls. A final-call constraint requires C to finish or abstain. The request-byte limit includes tool schemas and conversation history. All initial requests fit, including B's complete source texts.

If a C action has malformed arguments or unsupported citations, the controller saves the failure and returns validation feedback. The model can retrieve evidence, correct its submission, or abstain. Nothing from a rejected finish action is accepted. Original arguments remain in the raw response. Literal source checks, horizon checks, numerical evidence validation, and Decimal arithmetic are unchanged. Semantic support still requires human judgment.

Transport failures are terminal. There are no automatic network retries or configuration fallbacks. The budget journal saves the full wire body, including schemas and tool choice, under its `request.messages` envelope. It reserves a conservative amount before sending. A response saved before an interruption is reused only when the reconstructed request matches exactly. An uncertain request retains its reservation and blocks further paid execution pending inspection. A process lock prevents two runners from spending against one ledger concurrently.

The provider documents [strict native tools](https://api-docs.deepseek.com/guides/tool_calls/) at the beta endpoint. [Required or named tool choices](https://api-docs.deepseek.com/api/create-chat-completion/) require non-thinking mode. The completed pilot confirms that the provider accepted this configuration. The controller still rejected 18 valid responses containing two read-only searches because v3 required exactly one native call per response. The separate [v4 batching revision](earnings_protocol_v4.md) addresses that failure; the v3 source and recorded outcomes remain frozen.

## Frozen diagnostic population

The [configuration](../configs/earnings_protocol_v3.json) selects Q1–Q2 FY2025 for ADBE, INTU, SNPS, and BOX. Each has a saved v2 C JSON failure. This is a failure-oriented development diagnostic, not an unseen or representative test set.

Each pair has three synthetic controls: stale disclosure, all numerical tokens masked, and an appended pair of opposing statements. That gives four real pairs and twelve variants, or 32 B/C method runs. Stale variants must stop before model access. The remaining cases permit at most 108 model requests altogether. The missing-evidence control is broader than a table-only deletion; the contradiction wording is construction-known. These controls do not establish natural-conflict accuracy.

The pilot changes tool format, reasoning mode, output allowance, and validation feedback together. A successful pilot would show whether that combined implementation works operationally. It cannot identify which individual change caused an improvement. All attempts are retained; no best-attempt selection is allowed. Previously exposed held-out cases are not reused here. Any later rerun of them is a regression check, not fresh unseen validation.

## Cost and approval

[Preflight estimate](../reports/earnings-v3-preflight-2026-10-14/estimate.json): USD **0.5112** in a transparent planning scenario; USD **5.0575104** at every request's full input/output allowance with overhead. Proposed hard cap: **USD 6.00**. These are estimates, not charges or an invoice. Prices use the provider's [peak cache-miss rates](https://api-docs.deepseek.com/quick_start/pricing/), checked October 14: USD 0.30 per million input tokens and USD 1.20 per million output tokens. Cache and off-peak discounts are ignored.

The planning scenario assumes B uses 32,000 input and 3,000 output tokens per case, and C uses seven calls of 10,000 input and 1,000 output tokens each. The conservative bound instead uses all 108 allowed requests at the maximum request-byte and output-token limits plus 4,096 tokens of overhead. Actual usage is recorded, and a request is denied if its reservation exceeds the remaining approved cap.

The October 13 USD 8 approval belongs to the completed v2 benchmark. Nick approved this pilot's USD 6 cap on October 15; the [approval record](../reports/earnings-v3-preflight-2026-10-14/approval.json) binds its `freeze.json` hash. The original estimate and config retain their pre-approval status as immutable planning records. No approval file is created by preparation, and preparation does not load credentials.

## Reproduction

Run from the repository root with the project environment. No API key is needed for these checks:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
python scripts/verify_earnings_protocol_v3.py \
  --out reports/earnings-v3-validation-2026-10-14/scripted-traces --check
python scripts/earnings_benchmark.py --replay reports/earnings-v2-2026-10-13
python scripts/earnings_eval.py --replay reports/earnings-m1-m3-2026-10-13
```

Three saved [scripted traces](../reports/earnings-v3-validation-2026-10-14/scripted-traces/summary.json) demonstrate retrieval repairing unseen citations, termination after repeated invalid citations, and rejection of stale evidence before model access. Their responses are explicit fixtures, not model inference. They make zero network calls and zero paid calls.

Prepare a new directory without network access:

```bash
python scripts/earnings_protocol_v3.py --prepare reports/earnings-v3-new-preflight
```

The approved execution used an approval file with `approved: true`, `approved_by: "Nick"`, `max_usd`, and the SHA-256 of its `freeze.json`, plus the actual approval text and time. Its command was:

```bash
python scripts/earnings_protocol_v3.py \
  --run reports/earnings-v3-preflight-2026-10-14 \
  --approval work/earnings-v3-approval.json --env-file .env
```

The same command resumes completed responses and runs. Uncertain transport outcomes need inspection; do not delete journal records to force a retry. After execution, `--replay <bundle>` reproduces wire requests, citations, calculations, failures, and summary counts without model access. Replaying the model's saved response is distinct from reproducing live stochastic inference.

## Remaining acceptance work

Nick's 36 labels and sampled explanation judgments remain pending. Numerical output coverage and successful parsing cannot substitute for those judgments. Natural-conflict evidence, a table-only ablation, and fresh unseen validation remain separate research work. On October 15, Nick also approved retaining the macro workflow as a secondary section and replacing the public Jinde-origin paragraphs with neutral personal-project wording. Those documentation decisions are applied. No résumé file was edited or push made.
