# Macro corpus provenance

The macro corpus contains five Federal Reserve documents: the June, July, and September 2025 FOMC policy statements and the June and July meeting minutes. Separate release notices establish when the minutes became public.

| Source | Context date | Published at (UTC) | Use |
| --- | --- | --- | --- |
| June statement | 2025-06-18 | 2025-06-18 18:00 | Historical policy context |
| June minutes | 2025-06-18 | 2025-07-09 18:00 | July meeting dates and June discussion |
| July statement | 2025-07-30 | 2025-07-30 18:00 | Excluded from the July case; eligible for September |
| July minutes | 2025-07-30 | 2025-08-20 18:00 | September meeting dates and July discussion |
| September statement | 2025-09-17 | 2025-09-17 18:00 | Excluded from both pre-event cases |

Each source's URL and hashes are in [the manifest](../data/macro/manifest.json). No internship file, employer code, research report, or private strategy data was copied into this corpus.

## Capture method

The saved `.web.txt` files contain the browser reader's returned text with line markers. Direct HTTP access returned 403 during collection, so original HTML response bytes are not available. Long minutes required overlapping reader captures; later occurrences complete the earlier partial response.

`scripts/prepare_macro_data.py` deterministically selects the recorded article-body lines, removes reader citation markup, normalizes whitespace, and writes UTF-8 snapshots. It checks that every selected reader line is present. The selected minutes body ends before attendance; the statements end after the vote. Navigation and media-contact sections are excluded.

The manifest preserves the capture hash, snapshot hash, selected line range, and release-notice evidence. Re-running the script against the saved captures preserves the original capture timestamp. It is a normalization command, not a live collector.

All publication times are supported by the official releases' 2:00 p.m. EDT notices. Availability is provisionally set equal to release time; there is no independent first-observation log from 2025. Capture timestamps are from the actual 2026 collection.

## Cases and labels

The July case uses a July 25 cutoff for a July 28–August 1 window. The September case uses a September 12 cutoff for a September 15–19 window. Both cover the US market and the FOMC adapter only.

The July case is the development example. September is a temporal check. Its sources were inspected while building the project, so it is not a blinded holdout. The cases share event type and some historical context.

`labels.draft.json` contains two expected calendar event IDs and exact corpus hashes. The labels were prepared with AI assistance and have not been reviewed by Nick. They are not labels for risk interpretation, consensus, or causal market effects.

The corpus has no dedicated current-market-expectation document and no separately validated historical market-reaction series. The output must mark those gaps. Federal Reserve participants' views and past policy decisions are not interchangeable with current market consensus.

## Reproduction limits

`publication` mode provides a retrospective source-date filter. It does not prove that the captured text was unchanged since 2025. `snapshot` mode excludes sources captured after the requested cutoff. The strict mode therefore returns insufficient evidence for both stored cases.

The next dataset should be collected prospectively or from a verified point-in-time archive, with a genuinely unseen test period and human-reviewed claim support.
