# Scope of this document

This document covers the supporting earnings corpus. For the primary macro-event workflow, read [macro_data_provenance.md](macro_data_provenance.md).

---

# Source provenance and collection limits

Collected October 7, 2026, for local personal research. Exact UTC retrieval timestamps and SHA-256 hashes are in `data/manifest.json`. This is six source snapshots and three same-horizon comparison questions, not the old 20-document/15-pair planning target.

| Issuer | Release date | Reported quarter | Compared forecast | Primary source |
| --- | --- | --- | --- | --- |
| Adobe | 2025-06-12 | FY2025 Q2 | FY2025 annual revenue | [SEC issuer exhibit](https://www.sec.gov/Archives/edgar/data/796343/000079634325000064/adbeex991q225.htm) |
| Adobe | 2025-09-11 | FY2025 Q3 | FY2025 annual revenue | [SEC issuer exhibit](https://www.sec.gov/Archives/edgar/data/796343/000079634325000102/adbeex991q325.htm) |
| Salesforce | 2023-05-31 | FY2024 Q1 | FY2024 annual revenue | [SEC issuer exhibit](https://www.sec.gov/Archives/edgar/data/1108524/000110852423000021/crm-q1fy24xexhibit991.htm) |
| Salesforce | 2023-08-30 | FY2024 Q2 | FY2024 annual revenue | [SEC issuer exhibit](https://www.sec.gov/Archives/edgar/data/1108524/000110852423000037/crm-q2fy24xexhibit991.htm) |
| Autodesk | 2025-05-22 | FY2026 Q1 | FY2026 annual revenue | [Issuer release](https://investors.autodesk.com/index.php/news-releases/news-release-details/autodesk-inc-announces-fiscal-2026-first-quarter-results) |
| Autodesk | 2025-08-28 | FY2026 Q2 | FY2026 annual revenue | [Issuer release](https://investors.autodesk.com/news-releases/news-release-details/autodesk-inc-announces-fiscal-2026-second-quarter-results) |

## What a snapshot contains

Direct requests to SEC, Adobe's PDF host and Salesforce's PDF host returned HTTP 403. The available web reader retrieved primary-source rendered text. Reader outputs are preserved under `data/captures/`; UTF-8 line-number-stripped snapshots are under `data/snapshots/`. Hyperlink display labels are retained where available; tool citation markup is removed. No generated values are inserted into real snapshots.

`content_hash` hashes the exact saved normalized UTF-8 text. It does not claim to hash original HTML or PDF bytes. The raw reader capture retains collection metadata and line numbering. The reader's internal HTML normalization is external to the Python package and is not claimed reproducible from raw HTML. Offline execution is reproducible from the saved text and hashes.

The Adobe captures cover their 402 reader lines. Salesforce captures cover their released text through the financial appendices; a trailing blank line may be omitted. Autodesk Q1 includes the rendered release and appendix. Some page-navigation lines were folded by the reader. Autodesk Q2 contains lines through 509 of 667; later requests returned 403. Its main release, annual guidance row and heading are present, but part of the appendix is missing. `data/capture_audit.json` records exact reader coverage for the held-out sources. Do not describe that capture as the complete original filing.

The corpus is intentionally local. Review source rights and normalization before publishing or redistributing it. Original issuer notices remain in the captured text where included; source ownership is documented in `THIRD_PARTY_NOTICES.md`.

## Temporal policy

The releases establish publication dates rather than verified public-availability instants. For this experiment, both `published_at` and `available_at` use 23:59:59 New York time on that date. `timestamp_precision` names the assumption; `retrieved_at` is the actual collection time. Pair cutoffs are midnight immediately after the later release date.

`disclosure` mode enforces publication/assumed availability consistently at pipeline entry and both retrieval tools. `snapshot` mode also requires retrieval at or before the cutoff, so the old historical cutoffs reject this 2026 collection. There is no claim that current bytes were available at the historical cutoff, that a model has no memorized future facts, or that this is a leakage-free return-prediction experiment.

## Dataset selection and independence

Issuer separation was recorded before extraction tuning. The selected cases all raise annual revenue guidance; they were chosen to make the numerical workflow demonstrable. Selection/search snippets and draft labeling were AI-assisted. The held-out examples were not externally blinded. Synthetic challenges derive from Adobe development data and never increase the real document or event count.
