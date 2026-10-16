# Protocol findings from the frozen v2 run

The saved benchmark establishes an executed comparison, not a successful agent result. The next engineering priority is reliable model actions and evidence selection. Keep the current bundle unchanged so failures remain reproducible.

## Development evidence

All 12 development pairs completed before this diagnosis. B produced five numerical comparisons; its other seven runs stopped at `incomplete_model_output`. C produced four comparisons, seven JSON parse failures, and one completed abstention. The [execution analysis](../reports/earnings-v2-analysis-2026-10-13/analysis.md) reproduces these counts from saved runs. They are execution counts, not reviewed accuracy.

In the original Adobe development example, B used its entire 3,200-token output allowance. The provider reported 3,071 reasoning tokens, leaving an incomplete final answer. [Saved response](../reports/earnings-v2-2026-10-13/runs/ADBE-FY2025-Q2-Q3_B.json). C completed the same example with six calls and five retrieval actions; Python reproduced the USD 125 million midpoint increase. [Saved trace](../reports/earnings-v2-2026-10-13/runs/ADBE-FY2025-Q2-Q3_C.json).

Each of the seven development JSON failures begins with a parseable tool-action object followed by additional content. The strict parser rejects the complete response. The client already sends `response_format: {"type": "json_object"}` and explicitly requests JSON in the prompt; enabling that existing setting is not a new fix. The current controller does not trim trailing content, execute invented tool results, or count a parse failure as a successful abstention.

The shared metric validator also requires an exact contiguous horizon quotation. Output that changes wording or selects an unsupported period is rejected. Improving operational coverage must preserve that source check, rather than weakening it to make a results table larger.

## Next experiment boundaries

The completed synthetic test gives C five cases where both opposing statements were retrieved, but only one completed conflict flag with both citations, out of 24 cases. [Saved counts](../reports/earnings-v2-analysis-2026-10-13/analysis.json). The [Okta success](../reports/earnings-v2-2026-10-13/runs/OKTA-FY2025-Q2-Q3~v2-contradictory_commentary_C.json) uses seven model calls and six retrieval actions. The assertions are explicitly synthetic; this establishes one operational path, not general semantic-conflict accuracy.

1. Diagnose on the existing development issuers. A later rerun of these now-exposed held-out cases is a regression check, not new unseen-test evidence.
2. Test an explicitly versioned protocol with structural action constraints and a realistic answer-token budget. A non-thinking configuration is another diagnostic option, not a demonstrated improvement.
3. Keep B and C on the same model, evidence rules, and per-call provider configuration. Continue to report their different total call budgets.
4. Preserve raw responses, parser failures, rejected citations, and request reservations in a new bundle. Do not replace the v2 record or select the better attempt per case after seeing results.
5. Estimate and obtain approval for any new paid experiment. The October 13 approval binds to the v2 configuration; it is not a record of approval for a revised experiment.
6. Complete Nick's label and explanation reviews before reporting accuracy. More successful API calls alone do not establish the résumé's full research claims.

The provider documents [thinking-mode controls](https://api-docs.deepseek.com/guides/thinking_mode/) and [Chat Completions output limits and JSON output](https://api-docs.deepseek.com/api/create-chat-completion/). Those API capabilities do not substitute for an observed successful run of a revised protocol. No revised paid run was started for this diagnosis.

## October 14 implementation checkpoint

The [v3 development pilot](earnings_protocol_v3.md) now implements native function schemas, a non-thinking answer budget, and bounded validation feedback. Twenty-one new offline tests pass; the full suite has 180 passing tests. Three saved scripted traces reproduce recovery and stopping behavior. They are fixtures, not improved live-model results. All prior paid results remain intact and replay exactly. The new four-issuer pilot is frozen with a USD 0.5112 planning scenario, USD 5.0575104 conservative full-budget estimate, and proposed USD 6 cap. New approval is pending; no v3 paid request has been sent.

## October 15 paid results and batch correction

Nick approved the v3 pilot and it completed with 32 runs, 94 requests and USD 0.2376024 conservative token cost. All outputs and requests replay exactly. C completed three of four selected real cases and returned two numerical comparisons. It completed zero of four two-citation contradiction checks; all four failed to retrieve both expected synthetic statements. The [analysis](../reports/earnings-v3-analysis-2026-10-15/analysis.md) preserves these unsuccessful results.

No malformed finish-argument JSON was observed in this pilot, but C encountered 18 responses containing two valid read-only searches. V3 rejected all of them under its exactly-one-call rule. A separately versioned [batch correction](earnings_protocol_v4.md) now accepts atomic retrieval batches within the existing tool budget. Eight new tests include all 18 recorded action envelopes. This is offline regression evidence, not improved live-model behavior. The focused v4 live check is prepared and awaits a new approval; the full local suite has 188 passing tests.

## October 15 v4 execution and remaining evidence problems

Nick approved the frozen USD 3 v4 check. It completed all eight C runs and 43 requests for USD 0.1034148 conservative token cost, with exact offline replay. The [matched analysis](../reports/earnings-v4-analysis-2026-10-15/analysis.md) preserves every result and compares identical case/source hashes with v3. On four real development pairs, numerical outputs changed from two to three; both versions completed three without terminal errors. Across the four synthetic contradiction controls, valid two-citation flags changed from zero to one. These observations do not establish reviewed accuracy or an isolated causal improvement.

The controller accepted 22 of 27 multiple-function responses. Five batches exceeded the remaining seven-retrieval allowance and were rejected before execution. Calls across the matched eight cases changed from 57 in v3 to 43 in v4. No retrieval or model-call budget was enlarged.

The [BOX control](../reports/earnings-v4-preflight-2026-10-15/runs/BOX-FY2025-Q1-Q2~v3-contradictory_commentary_C.json) retrieved and cited both construction-known opposing statements. Its numerical result is separate from the conflict conclusion. This is a synthetic investigation example, not evidence that BOX management contradicted itself. The other three controls did not retrieve both statements. Most actions continued searching for numerical guidance; additional tool protocol success alone did not ensure explanation coverage.

Both [real](../reports/earnings-v4-preflight-2026-10-15/runs/SNPS-FY2025-Q1-Q2_C.json) and [synthetic](../reports/earnings-v4-preflight-2026-10-15/runs/SNPS-FY2025-Q1-Q2~v3-contradictory_commentary_C.json) Synopsys cases failed metric validation. Retrieved windows include a table with quarterly and fiscal-year low/high columns, a separate millions heading, and nonbreaking spaces. Rejected finish candidates changed whitespace, omitted units from the metric quotation, or combined incompatible quotation spans. The current validator also rejects a horizon quotation containing quarterly language, even when an annual column appears alongside it. A safe next implementation needs literal cell references and explicit column-to-period association; simply relaxing citation or quarterly checks would remove an important guard.

Do further engineering on development data before proposing another paid evaluation. Preserve all existing versions and failures. Nick's 36 label reviews and sampled explanation judgments remain necessary to measure accuracy. No next paid experiment is approved or started.

## October 15 v5 offline implementation

The [v5 protocol](earnings_protocol_v5.md) now uses source-bound metric/citation IDs, a separate structural proof for explicit annual table columns, and required guidance/explanation reviews for both disclosures. The model cannot alter selected values or quotation bytes. The old literal validator and prior protocols remain unchanged. C reserves four of its seven retrieval actions for required evidence reviews; optional searches cannot consume that reserve. B receives full disclosures and the same candidate catalogs in one call.

The full suite has 211 passing tests, including 23 new tests. Deterministic retrieval makes both injected statements available on all four development controls. Thirty-two explicitly scripted B/C traces replay exactly with no model inference or paid calls. Those traces test the controller; they do not establish model conflict accuracy. The new numerical catalog is shared deterministic assistance, so any later gain must not be credited solely to the agent loop.

The frozen 32-run B/C pilot has a USD 0.5112 planning scenario, USD 5.0575104 conservative full-budget estimate and proposed USD 5.50 cap. All initial B requests fit the existing byte limit. New paid approval is pending; none has been recorded or executed.

## October 15 v5 execution and explicit-reference correction

Nick approved the frozen USD 5.50 v5 pilot. It completed 32 B/C runs and 64 requests at USD 0.1967478 conservative token cost, with no uncertain requests. V3/v4/v5 combined cost is USD 0.5377650. The [complete analysis](../reports/earnings-v5-analysis-2026-10-15/analysis.md) replays all three bundles and compares every matched case. The original preparation files retain their historical pending status.

On the four real development pairs, both B and C produced four numerical outputs without terminal errors. C used 15 calls, compared with 19 in v4. The shared deterministic parser supplies a candidate for each source, including Synopsys' annual columns; the gain is not solely an agent reasoning result. Both methods passed all four broad numerical-mask controls and all four stale guards.

C retrieved both injected statements on all four contradiction controls, but both methods completed zero valid conflict flags. All eight runs failed citation reference validation. The model supplied quotation text in the ambiguous plain-string fields `statement_a` and `statement_b`; the resolver required IDs. Fifteen rejected conflict entries preserve this mismatch. Generic validation feedback did not consistently repair it. These are failures, not successful detections credited from prose.

A separate [v6 interface](earnings_protocol_v6.md) uses explicit `statement_a_id`/`statement_b_id` fields and enumerates the visible reference choices before each request. Local validation reports the precise invalid field. Nine new tests cover the saved mismatch, invisible IDs, empty choices and atomic publication; all 220 tests pass. Thirty-two scripted regression traces replay with no paid inference. V5 and its evidence module stay frozen.

The narrower v6 paid proposal includes only the four existing contradiction controls, both B/C: eight runs, at most 36 requests. Planning estimate USD 0.1704; conservative full-budget bound USD 1.6858368; proposed cap USD 1.75. Approval is pending; no v6 request has been sent.

Free-form prose still needs independent review. In [one saved BOX result](../reports/earnings-v5-analysis-2026-10-15/prose-arithmetic-note.json), the model says both bounds rose by USD 11 million, while the deterministic result correctly records USD 11 million and USD 10 million. This is a concrete inconsistency, not an exhaustive prose audit. Human label/support review, natural conflicts, table-only stress evaluation and fresh unseen validation remain outstanding.

## October 15 completed v6–v10 evidence

Nick's continuing authorization preserves USD 0.50 of the current USD 6 allocation and replaces historical per-run confirmation requirements within that allocation. Frozen estimates, allocations and all request reservations are saved. [The final checkpoint](../reports/earnings-evidence-v10-2026-10-15/evidence.md) reports USD 3.2684346 spent or reserved, leaving USD 2.7315654 in the allocation and USD 2.2315654 further authorized spend. One v7 request retains USD 0.0374805 of uncertain billing; it was never retried. Later execution continued only unattempted cases, with old request/run hashes preserved.

V6's explicit reference fields completed all four selected contradiction controls for both B/C. V7 then saved 288 full-corpus/table-ablation outcomes; v8 saved another 288 with an independently versioned point-target screen. V8 filters a monetary headwind that was incorrectly admitted as an absolute revenue target. C produces 15/24 numerical outputs on the original held-out real pairs and completes all 24 without terminal controller errors; D produces 14/24. These are now-exposed regression counts with different parser assistance, not accuracy or isolated agent superiority.

V9 reproduces the original 72 synthetic stress inputs plus two natural supplements, all four methods. C completes 24/24 valid two-citation synthetic conflict flags, 24/24 broad missing-number abstentions and 24/24 stale guards. B completes 21/24, 22/24 and 24/24. Two B contexts exceed the fixed input limit; three B conflict attempts fail reference selection. Failed attempts stay in the denominators. The separate table-row ablations retain prose and therefore have no blanket expected abstention label.

V10 recognizes the natural explicit full-year financial-guidance withdrawal, inheriting identity from the unique prior revenue target while leaving bounds absent. Both B/C live results show `guidance_withdrawn`; the rollover remains an abstention. Its new controller also replays 290 non-withdrawal recordings unchanged. All 884 new v6–v10 method outcomes and 951 request records, including the retained failed request, replay offline. The full local suite has 251 passing tests.

All 36 natural labels remain pending. A new deterministic sample contains 33 natural explanation/conflict candidates, also pending. The sole B natural conflict candidate puts an ordinary numerical revision in its conflict array while its own reason says it is not a conflict; C emits no natural conflict candidate on those 24 real pairs. This is not validated natural-conflict performance. The offline case-report generator recomputes numerical tables and keeps unreviewed model prose in the linked raw traces. No résumé file edit, push or new remote CI result occurred.
