# V6: explicit conflict reference choices

The [v5 pilot](../reports/earnings-v5-analysis-2026-10-15/analysis.md) fixed the observed table extraction and retrieval failures on four selected development pairs. Both B and C produced four numerical outputs. C retrieved both synthetic opposing statements in every contradiction control. However, all eight B/C contradiction runs ended with a citation-ID validation failure.

The saved responses expose an interface ambiguity: `statement_a` and `statement_b` were unconstrained strings, but the resolver expected evidence IDs. Fifteen rejected conflict entries contain quotation text in those fields. A generic citation error did not identify which field needed repair. These attempts are retained as failures, even when the model's prose discusses the intended contradiction.

## Separate interface correction

[V6](../src/eventlens/protocol_v6.py) uses `statement_a_id` and `statement_b_id`, with field descriptions that explicitly require retrieved evidence IDs. Before each model request, the finish schema enumerates the currently visible metric and citation IDs. This applies to metrics, explanations, both conflict statements and comparability evidence. Local validation applies the same enum and reports the specific invalid field path.

Only successfully published tool results contribute IDs. Merely computing a catalog or reading part of a failed atomic batch exposes no choices. A successful later search refreshes the next request's enum. When no choices exist, the schema uses a sentinel to avoid an empty enum; the model must return empty collections, and the evidence resolver never accepts the sentinel as evidence. Exact source hashes, offsets, visibility, annual-column proofs, distinct conflict quotations and deterministic arithmetic still apply.

The evidence parser and ranking are imported unchanged from v5. Model, provider settings, eight-call/seven-retrieval C budget, two repair limit, 6,000 output-token limit and 128,000-byte input cap are unchanged. B remains one call with full sources and the same catalogs. V2–v5 code and completed results remain frozen. The default CLI is unchanged.

## Offline evidence

- **220 tests pass**, including nine new v6 tests. The tests reject the 15 recorded quote-valued conflict entries with a specific field error, reject invented references and verify that a failed batch exposes no reference choices. [Test log](../reports/earnings-v6-validation-2026-10-15/tests.log).
- **32 scripted B/C regression traces** cover the previous real, stale, missing-evidence and contradiction inputs. All replay exactly with zero network/paid calls. Their conflict choices use construction-known fixture expectations, so they are not live model results. [Scripted verification](../reports/earnings-v6-validation-2026-10-15/scripted/verification.json).
- The complete paid v5 pilot still replays, as do the matched v3/v4 bundles. [V5 analysis](../reports/earnings-v5-analysis-2026-10-15/analysis.json).

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
python scripts/verify_earnings_protocol_v6.py reports/earnings-v6-preflight-2026-10-15 \
  --out reports/earnings-v6-validation-2026-10-15/scripted --check
```

## Focused paid check — completed

Nick authorized continuing within the USD 6 improvement allocation while preserving USD 0.50. The frozen v6 check completed **eight runs, 16 requests and USD 0.0570054** conservative token cost. Both B and C produced valid two-citation flags on all four synthetic controls, retained their numerical comparisons and had no terminal or validation errors. All requests/results replay exactly. [Complete matched v5/v6 analysis](../reports/earnings-v6-analysis-2026-10-15/analysis.md). Combined v3–v6 spend is USD 0.5947704.

The [frozen pilot](../reports/earnings-v6-preflight-2026-10-15/estimate.json) reruns only the four existing synthetic contradiction controls, with both B and C: **eight method/case runs, at most 36 requests**. It adds no unseen data. The largest initial request is 122,601 bytes, below the unchanged cap. Later context growth is checked before every request.

| Cost measure | USD |
| --- | ---: |
| Planning scenario | 0.1704 |
| Conservative full-budget estimate | 1.6858368 |
| Proposed hard cap | 1.75 |
| Completed v3/v4/v5 cost | 0.5377650 |
| Prior cost plus proposed cap | 2.2877650 |

The planning scenario assumes one B request with 32,000 input/3,000 output tokens and seven C requests with 10,000 input/1,000 output tokens per control. The conservative bound uses every maximum-size request plus overhead. Prices are the frozen October 15 DeepSeek peak cache-miss rates: USD 0.30/M input and USD 1.20/M output, without discounts. The combined cap remains within the earlier USD 6 allocation.

The saved [approval](../reports/earnings-v6-preflight-2026-10-15/approval.json) binds freeze SHA-256 `8f6172ee1bba8821c967785bdb9a442ffe7694dc974712df6b1e6a4bb1c979fe`. Original preflight fields preserve the earlier pending state. Reproduce the completed experiment offline:

```sh
python scripts/analyze_earnings_protocol_v6.py --check
```

## Interpretation limits

This is an interface regression check on exposed synthetic controls. Its success does not prove natural-conflict accuracy, evidence entailment or a general agent advantage. Both B and C succeeded. Free-form model explanations and unresolved text remain unvalidated prose; v5 includes a numeric inconsistency in that prose despite correct deterministic arithmetic. Nick's labels/support judgments and fresh unseen validation remain necessary. The [v7 corpus and table-row test](earnings_expansion_v7.md) extends coverage using the same frozen v6 controller.
