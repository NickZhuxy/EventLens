# V3 development reliability pilot

Failure-oriented development diagnostic. No human-reviewed accuracy or unseen-test result.

Completed **32 method runs** and **94 model requests**. Conservative token cost: **USD 0.2376024**, under the approved USD 6 cap. Exact replay made zero network or paid calls.

## Operational results

| Method | Case type | n | Completed without errors | Numeric outputs | Valid control outcomes | Terminal errors | Recovered runs | Calls |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| B | contradictory_commentary | 4 | 2 | 2 | 1 | 2 | 0 | 4 |
| B | missing_numerical_evidence | 4 | 1 | 0 | 1 | 3 | 0 | 4 |
| B | real | 4 | 2 | 2 | unreviewed | 2 | 0 | 4 |
| B | stale_disclosure | 4 | 0 | 0 | 4 | 4 | 0 | 0 |
| C | contradictory_commentary | 4 | 3 | 2 | 0 | 1 | 3 | 32 |
| C | missing_numerical_evidence | 4 | 2 | 0 | 2 | 2 | 2 | 25 |
| C | real | 4 | 3 | 2 | unreviewed | 1 | 2 | 25 |
| C | stale_disclosure | 4 | 0 | 0 | 4 | 4 | 0 | 0 |

Stale-source rejections are expected pre-model eligibility failures. Other failures are never credited as valid control outcomes. Recovered runs can finish without numerical output; real-case correctness is unreviewed.

## Same real development pairs in v2 and v3

| Case | Method | v2 numeric | v3 numeric | v2 terminal failure | v3 terminal failure | v2 calls | v3 calls |
| --- | --- | --- | --- | --- | --- | ---: | ---: |
| ADBE-FY2025-Q1-Q2 | B | True | True | False | False | 1 | 1 |
| ADBE-FY2025-Q1-Q2 | C | False | True | True | False | 1 | 7 |
| BOX-FY2025-Q1-Q2 | B | False | True | True | False | 1 | 1 |
| BOX-FY2025-Q1-Q2 | C | False | False | True | False | 1 | 7 |
| INTU-FY2025-Q1-Q2 | B | True | False | False | True | 1 | 1 |
| INTU-FY2025-Q1-Q2 | C | False | True | True | False | 2 | 4 |
| SNPS-FY2025-Q1-Q2 | B | False | False | True | True | 1 | 1 |
| SNPS-FY2025-Q1-Q2 | C | False | False | True | True | 2 | 7 |

This comparison diagnoses the same exposed development inputs. It does not isolate a causal effect of native tools or establish generalization.

## Remaining failures

### B

Multiple-function responses: 0. Native envelope errors: 0. Unparseable finish arguments: 0.

Recovered to numerical output: 0; recovered without numerical output: 0.

Provided-metric attempts attributed to the absent new source: 0. This audit includes parseable rejected finish actions; it is not a general fabrication score.

- 1: `citation_not_literal`
- 2: `metric_validation: nonliteral_evidence, nonliteral_horizon_evidence, unit_not_in_quote, horizon_not_supported, citation_not_in_retrieved_context`
- 1: `metric_validation: nonliteral_evidence, nonliteral_horizon_evidence, value_not_in_quote, horizon_not_supported, citation_not_in_retrieved_context`
- 1: `metric_validation: nonliteral_evidence, nonliteral_horizon_evidence, disconnected_horizon_evidence, value_not_in_quote, unit_not_in_quote, quarterly_or_ambiguous_horizon, citation_not_in_retrieved_context`
- 2: `metric_validation: nonliteral_evidence, nonliteral_horizon_evidence, unit_not_in_quote, quarterly_or_ambiguous_horizon, citation_not_in_retrieved_context`

### C

Multiple-function responses: 18. Native envelope errors: 18. Unparseable finish arguments: 0.

Recovered to numerical output: 3; recovered without numerical output: 4.

Provided-metric attempts attributed to the absent new source: 0. This audit includes parseable rejected finish actions; it is not a general fabrication score.

- 1: `expected_one_native_tool_call`
- 3: `metric_validation: nonliteral_evidence, nonliteral_horizon_evidence, unit_not_in_quote, quarterly_or_ambiguous_horizon, citation_not_in_retrieved_context`

Cases with both expected synthetic statements in retrieved context: 0/4.

## Saved investigation examples

- [repaired real comparison](../earnings-v3-preflight-2026-10-14/runs/ADBE-FY2025-Q1-Q2_C.json)

Read validation feedback and subsequent retrieval actions in the trace. No successful two-citation C conflict example was produced in this pilot.

## Limits

- Four selected development pairs, not an independent sample or unseen test.
- Tool format, prompts, reasoning mode, output allowance and validation feedback changed together.
- A completed abstention after repair is operational recovery, not proof that abstention was correct on real data.
- Missing-evidence controls mask every numeric token, not just a table. Contradictions use known synthetic wording.
- All labels and semantic explanation judgments remain pending. Literal citations are not semantic entailment.
- Cost uses reported tokens at peak cache-miss prices and is not an invoice.

## Reproduce

From the repository root:

```sh
python scripts/analyze_earnings_protocol_v3.py reports/earnings-v3-preflight-2026-10-14 --out reports/earnings-v3-analysis-2026-10-15 --check
```
