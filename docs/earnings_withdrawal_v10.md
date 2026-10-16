# V10: explicit annual financial-guidance withdrawal

The natural Synopsys notice explicitly suspends financial guidance for both its quarter and full fiscal year. Earlier parsers required a revenue noun and rejected quarterly wording even when the statement also named the full year, so the result was only `missing_guidance`.

The new [evidence module](../src/eventlens/evidence_v10.py) admits a narrow, explicit full-year financial-guidance suspension. It binds the exact withdrawal statement and annual scope to the unique prior accepted revenue target. Currency, basis, definition and units are inherited from that prior target and identified as inherited in the tool response. No replacement bounds or numerical delta are inferred. Negated, hypothetical, partial-metric, quarterly-only, wrong-year and unsupported statements abstain. It does not override the old evidence validator.

[Four live B/C results](../reports/earnings-v10-analysis-2026-10-15/analysis.md) cover the two original supplemental cases. Both methods identify the withdrawal, retain absent bounds, and continue to abstain on the fiscal-year rollover. Eight provider requests cost USD 0.0232560 under a USD 0.25 cap; all replay exactly. The planning estimate was USD 0.03279130. No uncertain request was added.

The seven new tests cover explicit scope, inherited identity, absent numerical values, negative controls, registry tampering, and unchanged catalogs on the full existing corpus/stress inputs. The full local suite has 251 passing tests. The [recorded regression](../reports/earnings-v10-validation-2026-10-15/recorded-regression.json) re-executes 290 non-withdrawal v8/v9 B/C recordings through v10 with identical requests, traces, evidence and outcomes. This is offline controller regression, not fresh model inference on the full corpus. Four additional scripted traces are labeled fixtures. Human labels and semantic review remain pending.

```sh
python scripts/analyze_earnings_withdrawal_v10.py --check
python scripts/verify_earnings_withdrawal_regression_v10.py --check
python scripts/earnings_evidence_index_v10.py --check
```

The [case report](../reports/earnings-examples-2026-10-15/synopsys-withdrawal.md) shows the prior annual table and exact withdrawal statement. The default historical CLI and all older protocol modules remain unchanged; the versioned experiment runners identify the controller used.
