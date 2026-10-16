# Saved retrieval example: Adobe FY2025 Q2 to Q3

This is a development example from the original pilot. It illustrates the execution trace and does not estimate benchmark accuracy.

Source run: `reports/earnings-v2-2026-10-13/runs/ADBE-FY2025-Q2-Q3_C.json`.

Model calls: 6. Conclusion: `supported`. Controller errors: `[]`.

## Retrieved evidence

[ADBE-2025-Q2](https://www.sec.gov/Archives/edgar/data/796343/000079634325000064/adbeex991q225.htm):

> The following updated table summarizes Adobe’s fiscal year 2025 targets, which assumes current macroeconomic conditions2:
>  |  |  |  |  |  |  |  |
> Total revenue  | $23.50 billion to $23.60 billion

Saved source hash: `99e83a21cac144ba1d31481534ba6658a0f4bf7016b842510b5a36b4c0e5a24b`. Metric validation: `pass`.

[ADBE-2025-Q3](https://www.sec.gov/Archives/edgar/data/796343/000079634325000102/adbeex991q325.htm):

> The following updated table summarizes Adobe’s fiscal year 2025 targets, which assumes current macroeconomic conditions2:
>  |  |  |  |  |  |  |  |
> Total revenue  | $23.65 billion to $23.70 billion

Saved source hash: `e504dd9473b01c3a3a8b7a5c481a4e54b5f0cd91bbee7ed9300d168f72b4fc2c`. Metric validation: `pass`.

## Python calculation

Old midpoint: USD 23550000000.00. New midpoint: USD 23675000000.00. Change: USD 125000000.00.

These values come from the validated ranges. The model does not supply the arithmetic result.

## Retrieval actions

| Step | Tool | Arguments |
| ---: | --- | --- |
| 1 | `search_passages` | `{"query": "fiscal 2025 total revenue guidance", "source_id": "ADBE-2025-Q2"}` |
| 2 | `search_passages` | `{"query": "FY25 total revenue target annual fiscal year 2025", "source_id": "ADBE-2025-Q2"}` |
| 3 | `get_source` | `{"end": 6500, "source_id": "ADBE-2025-Q2", "start": 3500}` |
| 4 | `search_passages` | `{"query": "fiscal year 2025 total revenue targets annual", "source_id": "ADBE-2025-Q3"}` |
| 5 | `get_source` | `{"end": 6500, "source_id": "ADBE-2025-Q3", "start": 3500}` |

Each returned passage and every model request and response are in the source run. Explanation support still requires human review.
