# Earnings benchmark execution analysis

Completed method/case runs: 440; request attempts: 342; conservative cost: USD 1.3671111.

Peak price with every input token treated as a cache miss; uncertain requests retain the full reservation. Not an invoice.

Counts are coverage and engineering evidence. No natural-case accuracy or superiority claim until human label and explanation review.

| Method | Split | n | Numerical outputs | Conflict flags | Abstentions | Calls | Median seconds | Truncated calls |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A | development | 12 | 5 | 0 | 7 | 0 | 0.007 | 0 |
| A | heldout | 24 | 2 | 0 | 22 | 0 | 0.005 | 0 |
| A | supplemental_natural | 2 | 0 | 0 | 2 | 0 | 0.002 | 0 |
| A | synthetic_heldout | 72 | 2 | 24 | 48 | 0 | 0.004 | 0 |
| B | development | 12 | 5 | 0 | 7 | 12 | 17.131 | 7 |
| B | heldout | 24 | 4 | 0 | 20 | 24 | 15.81 | 11 |
| B | supplemental_natural | 2 | 0 | 0 | 2 | 2 | 18.13 | 2 |
| B | synthetic_heldout | 72 | 2 | 2 | 70 | 48 | 14.394 | 28 |
| C | development | 12 | 4 | 0 | 8 | 38 | 7.422 | 0 |
| C | heldout | 24 | 4 | 0 | 20 | 76 | 10.385 | 2 |
| C | supplemental_natural | 2 | 0 | 0 | 2 | 11 | 26.0 | 0 |
| C | synthetic_heldout | 72 | 2 | 1 | 70 | 131 | 2.405 | 4 |
| D | development | 12 | 5 | 0 | 7 | 0 | 0.023 | 0 |
| D | heldout | 24 | 14 | 0 | 10 | 0 | 0.021 | 0 |
| D | supplemental_natural | 2 | 0 | 0 | 2 | 0 | 0.014 | 0 |
| D | synthetic_heldout | 72 | 14 | 17 | 55 | 0 | 0.017 | 0 |

## Stress controls with execution failures excluded from success

Valid expected decisions require the expected status and no controller errors, except the intended stale-pair eligibility rejection. Rejected metric candidates remain separately visible. All attempted runs remain in the denominator; these are construction-known synthetic controls, not reviewed natural labels.

| Method | Control | n | Raw status matches | Valid expected decisions | Both expected citations | Absent-source metric candidates |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| A | contradictory_commentary | 24 | 24 | 24 | 24 | n/a |
| A | missing_table | 24 | 24 | 24 | n/a | 0 |
| A | stale_disclosure | 24 | 24 | 24 | n/a | 0 |
| B | contradictory_commentary | 24 | 2 | 2 | 2 | n/a |
| B | missing_table | 24 | 24 | 9 | n/a | 0 |
| B | stale_disclosure | 24 | 24 | 24 | n/a | 0 |
| C | contradictory_commentary | 24 | 1 | 1 | 1 | n/a |
| C | missing_table | 24 | 24 | 5 | n/a | 0 |
| C | stale_disclosure | 24 | 24 | 24 | n/a | 0 |
| D | contradictory_commentary | 24 | 17 | 17 | 17 | n/a |
| D | missing_table | 24 | 24 | 24 | n/a | 0 |
| D | stale_disclosure | 24 | 24 | 24 | n/a | 0 |

## Failure categories

- A / synthetic_heldout: controller errors {"stale_or_reversed_disclosure_pair": 24}; metric-screen errors {}.
- B / development: controller errors {"incomplete_model_output": 7}; metric-screen errors {}.
- B / heldout: controller errors {"calendar/horizon mismatch": 2, "citation_not_in_supplied_context": 4, "incomplete_model_output": 11}; metric-screen errors {"horizon_not_supported": 4, "quarterly_or_ambiguous_horizon": 2}.
- B / supplemental_natural: controller errors {"incomplete_model_output": 2}; metric-screen errors {}.
- B / synthetic_heldout: controller errors {"calendar/horizon mismatch": 3, "citation_not_in_supplied_context": 6, "incomplete_model_output": 28, "stale_or_reversed_disclosure_pair": 24}; metric-screen errors {"horizon_not_supported": 1, "quarterly_or_ambiguous_horizon": 1}.
- C / development: controller errors {"Extra data: line 1 column 184 (char 183)": 1, "Extra data: line 1 column 187 (char 186)": 1, "Extra data: line 3 column 1 (char 175)": 1, "Extra data: line 3 column 1 (char 192)": 1, "Extra data: line 3 column 1 (char 197)": 1, "Extra data: line 3 column 1 (char 199)": 1, "Extra data: line 3 column 1 (char 211)": 1}; metric-screen errors {}.
- C / heldout: controller errors {"Extra data: line 1 column 190 (char 189)": 1, "Extra data: line 1 column 213 (char 212)": 1, "Extra data: line 2 column 1 (char 206)": 1, "Extra data: line 3 column 1 (char 184)": 1, "Extra data: line 3 column 1 (char 185)": 1, "Extra data: line 3 column 1 (char 190)": 2, "Extra data: line 3 column 1 (char 191)": 1, "Extra data: line 3 column 1 (char 192)": 1, "Extra data: line 3 column 1 (char 196)": 1, "Extra data: line 3 column 1 (char 211)": 1, "citation_not_in_retrieved_context": 1, "citation_not_in_supplied_context": 4, "citation_not_literal": 1, "incomplete_model_output": 2}; metric-screen errors {"horizon_not_supported": 2}.
- C / supplemental_natural: controller errors {"citation_not_in_supplied_context": 1}; metric-screen errors {}.
- C / synthetic_heldout: controller errors {"Extra data: line 1 column 178 (char 177)": 1, "Extra data: line 1 column 182 (char 181)": 1, "Extra data: line 1 column 190 (char 189)": 2, "Extra data: line 1 column 191 (char 190)": 2, "Extra data: line 1 column 194 (char 193)": 2, "Extra data: line 1 column 196 (char 195)": 1, "Extra data: line 1 column 204 (char 203)": 1, "Extra data: line 1 column 210 (char 209)": 1, "Extra data: line 1 column 216 (char 215)": 1, "Extra data: line 3 column 1 (char 179)": 1, "Extra data: line 3 column 1 (char 186)": 1, "Extra data: line 3 column 1 (char 187)": 1, "Extra data: line 3 column 1 (char 189)": 1, "Extra data: line 3 column 1 (char 192)": 1, "Extra data: line 3 column 1 (char 194)": 1, "Extra data: line 3 column 1 (char 196)": 1, "Extra data: line 3 column 1 (char 197)": 1, "Extra data: line 3 column 1 (char 198)": 1, "Extra data: line 3 column 1 (char 207)": 1, "Extra data: line 3 column 1 (char 217)": 1, "Extra data: line 3 column 1 (char 221)": 1, "Extra data: line 3 column 1 (char 226)": 1, "Extra data: line 3 column 1 (char 228)": 1, "citation_not_in_supplied_context": 7, "citation_not_literal": 4, "incomplete_model_output": 4, "stale_or_reversed_disclosure_pair": 24}; metric-screen errors {"horizon_not_supported": 1, "quarterly_or_ambiguous_horizon": 1}.
- D / heldout: controller errors {}; metric-screen errors {"horizon_not_supported": 5}.
- D / synthetic_heldout: controller errors {"stale_or_reversed_disclosure_pair": 24}; metric-screen errors {"horizon_not_supported": 5}.

An output-limit failure is reported as a failed attempt, not a successful abstention or proof that a model cannot extract the answer. The same frozen per-call limit applies to B and C, but B must complete the entire task in one response; this budget can disadvantage B. The comparison is not compute matched.
The missing-table control removes all numerical content, including headings and actuals. It measures behavior under broad missing numerical evidence, not isolated table removal. Contradictory-control assertions are synthetic. Natural explanation support remains unreviewed.
Absent-source metric counts cover extracted candidates, including candidates rejected by the metric screen. A malformed response or an earlier controller rejection can prevent candidate extraction. Zero counted candidates therefore does not establish zero fabrication across all raw model text; failed attempts remain failures.
The contradiction controls use a known opposite-polarity template. Its vocabulary appears in the C search hint and the A/D lexical checker. Their scores test retrieval, protocol handling and citation validation for this known construction; they do not establish generalization to unseen natural contradictions.
For each saved C example, inspect its tool requests, returned passages, final quotations and Python validation in the source bundle. The analysis retains failed cases rather than selecting only successful examples.
