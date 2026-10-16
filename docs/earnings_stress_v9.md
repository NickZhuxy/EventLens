# V9: expanded stress regression

V9 applies the unchanged v8 model controller and candidate parser to the original v2 stress inputs: 24 stale disclosures, 24 broad numerical removals, and 24 synthetic opposing-commentary controls. It also includes the two original supplemental natural withdrawal/rollover examples. Four methods produce 296 saved outcomes. Source text, case metadata and transformations are byte-identical to the original bundle.

The old `missing_table` name means that all numerical tokens were removed, including prose and year headings. It does not mean table-only deletion. The separate v7/v8 experiment deletes only pipe-bearing physical rows and retains all other text. All cases are now exposed regression inputs. Natural explanation support, natural conflicts and numerical accuracy still require human review.

The [preflight](../reports/earnings-v9-2026-10-15/initial_request_sizes.json) records two Salesforce B inputs that exceed the fixed 128,000-byte limit. The full-document baseline remains unchanged and these attempts stay in the denominator. Stale inputs reject before any provider request. A/D remain deterministic and must reproduce their original outcomes.

The planning estimate is USD 0.81978250 and the hard cap is USD 1.75 under the continuing USD 6 allocation, preserving USD 0.50. The unconstrained maximum of 450 maximum-size requests is not authorized. All existing uncertain charges remain reserved, with identical uncertain requests blocked before transmission.

## Reproduce

The [analysis](../reports/earnings-v9-analysis-2026-10-15/analysis.md) credits only completed appropriate decisions; a controller failure or input-limit failure is not a successful abstention. A synthetic conflict requires both construction-known quotations in a valid final conflict record. This does not establish accuracy on natural management contradictions.

```sh
python scripts/analyze_earnings_stress_v9.py --check
python scripts/verify_earnings_stress_v9.py reports/earnings-v9-2026-10-15 \
  --out reports/earnings-v9-validation-2026-10-15/scripted --check
```

The offline verifier produces 148 explicitly scripted B/C traces using construction-known expectations. It makes no paid calls. Its choices and catalog-availability counts are not live model performance.

## Completed result

The 296 outcomes and 238 provider requests replay exactly at USD 0.7021698 conservative cost, with no uncertain requests. C completes all 24 known conflict controls with both citations, all 24 missing-number abstentions, and all 24 stale guards. B completes 21, 22 and 24 respectively. The two natural supplemental cases abstained with `missing_guidance`; the separate [v10 check](earnings_withdrawal_v10.md) subsequently addresses explicit annual withdrawal. No prior output is replaced.
