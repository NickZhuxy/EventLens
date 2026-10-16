# V4: bounded batches of native retrieval calls

The [completed v3 pilot](../reports/earnings-v3-analysis-2026-10-15/analysis.md) rejected 18 responses that each contained two valid `search_passages` calls. They were read-only searches within the allowed disclosure pair. The exactly-one-call constraint consumed repair budget before retrieval. No C contradiction case retrieved both expected synthetic statements, and none completed a two-citation flag.

The new [v4 controller](../src/eventlens/protocol_v4.py) accepts a batch of independent read-only native retrieval calls. Each retrieval counts against the original seven-tool budget. All envelopes and schemas are checked before execution; results become visible to the model only if the entire batch succeeds. An invalid batch contributes no accepted evidence. `finish` must be submitted alone. Duplicate call IDs, mixed finish/retrieval batches, malformed arguments, out-of-pair sources, and batches exceeding the remaining budget are rejected. Each accepted call receives a matching native tool response.

No numerical validator, quote requirement, cutoff, source set, retrieval ranking, model, pricing, or per-call generation setting changes. C's prompt now allows retrieval batches; B's prompt is unchanged. This isolates the batch-handling change more narrowly than v3's combined protocol changes. The implementation is versioned separately to retain exact v2 and v3 replay.

## Offline evidence

Eight new tests cover batch execution, atomic evidence visibility, budget exhaustion, mixed actions, duplicate IDs, full-request replay, and the new pilot's approval boundary. They exercise all 18 recorded multi-search responses. Those saved actions execute successfully under the new controller in fixtures followed by a scripted finish. This is an action-handling regression test, not a replay of a changed live model conversation or proof of improved research quality.

```sh
PYTHONPATH=src python -m unittest discover -s tests -p test_protocol_v4.py -v
```

## Completed focused live check

The [frozen preflight](../reports/earnings-v4-preflight-2026-10-15/estimate.json) contains eight C jobs: the same four real development pairs and their four existing synthetic contradiction controls. B is not rerun; its v3 results remain available as the baseline. This is still development evidence. The data were already exposed, the synthetic wording is known, and human labels remain pending.

- Planning scenario: **USD 0.2352**, assuming seven calls per case with 10,000 input and 1,000 output tokens per call.
- Conservative full-budget estimate: **USD 2.9970432**, covering all 64 allowed requests at the full byte/output limits plus overhead.
- Approved hard cap: **USD 3.00**. Nick approved this frozen experiment on October 15. Prices use peak cache-miss rates, ignoring discounts.
- Completed: **8 C runs, 43 requests, USD 0.1034148** conservative token cost; zero uncertain requests. V3 and v4 together cost USD 0.3410172 under the prior USD 6 allocation. The [approval](../reports/earnings-v4-preflight-2026-10-15/approval.json) binds v4's freeze hash; the v3 approval remains invalid for this experiment.

The approved execution used:

```sh
python scripts/earnings_protocol_v4.py \
  --run reports/earnings-v4-preflight-2026-10-15 \
  --approval work/earnings-v4-approval.json --env-file .env
```

The journal, reservation checks, process lock, exact response reuse, and offline replay follow the v3 workflow. All attempts remain in the bundle, including failed or empty outputs. Reproduce the saved results without credentials or paid calls:

```sh
python scripts/analyze_earnings_protocol_v4.py reports/earnings-v4-preflight-2026-10-15 \
  --out reports/earnings-v4-analysis-2026-10-15 --check
```

## Measured outcome

The [matched analysis](../reports/earnings-v4-analysis-2026-10-15/analysis.md) compares the same eight cases and source hashes. On the four real pairs, v4 C produced three numerical outputs versus two in v3; both versions completed three without terminal errors. Model calls fell from 25 to 19. On the four synthetic contradiction controls, valid two-citation flags changed from zero to one and calls from 32 to 24. These are selected development observations, not reviewed accuracy or an isolated causal estimate.

V4 accepted 22 of 27 multiple-function responses. Five batches were rejected because they exceeded the remaining retrieval budget. The successful BOX control retrieved both synthetic statements and finished with both citations. The other three controls never retrieved both statements. Both Synopsys cases ended in metric validation errors. Its mixed quarterly/annual table needs explicit column grounding as well as literal quotation handling; relaxing the existing horizon check would conceal ambiguity.

The approved pilot is complete. No further paid experiment is authorized by this approval. Human label and explanation review, table-only deletion, natural-conflict evaluation, and fresh unseen validation remain separate work.
