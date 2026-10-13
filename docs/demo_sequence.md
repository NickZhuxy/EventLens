# Reproducible macro demo

Run these commands from the installed project root. Use new output directories if these already exist.

```sh
eventlens macro validate
eventlens macro brief --case july-2025-fomc --out work/demo-july
eventlens macro mock-demo --repair --out work/demo-repair
eventlens macro brief --case july-2025-fomc --cutoff-mode snapshot --out work/demo-strict
eventlens macro evaluate --out work/demo-evaluation
```

1. Open the July brief. Identify the calendar date evidence, historical policy context, and missing current consensus.
2. Open the repair run's JSON. Find `list_events`, `search_sources`, `read_source`, and the two `draft_validation` entries. The first must fail and the second must pass. State that these choices are scripted.
3. Open the strict-mode brief. There are no eligible 2025 captures because collection occurred in 2026. This is an evidence boundary, not a no-risk conclusion.
4. Open the evaluation report. The rule baseline is measured; live methods and semantic support remain unmeasured.

When a model is configured, run:

```sh
eventlens macro evaluate --live --model YOUR_MODEL_ID --out work/demo-live
```

Review every produced claim and preserve unsuccessful runs. A successful API call alone does not demonstrate accurate financial interpretation.
