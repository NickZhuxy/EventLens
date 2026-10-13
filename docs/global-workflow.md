# Global macro research workflow

The operational unit is a time-window risk brief, supported by a full event table. An analyst supplies markets and a question; the service freezes eligible source versions; one model researches and selects up to eight events. The output is intended to be short enough to read as an email body. EventLens does not send it automatically.

## Coverage and dates

`GET /v1/catalog` returns 41 catalog entries and their reference URLs. These links are research entry points, not evidence for a particular occurrence or market reaction. Research priority is a configurable code-level default, not a measured volatility score. US unemployment and nonfarm payrolls share one Employment Situation occurrence. CPI and PPI remain distinct releases.

Market codes are `CN`, `HK`, `TW`, `SEA`, `EU`, `US`, `JP`, and `GLOBAL`. `GLOBAL` selects the full universe; a source tagged `GLOBAL` is also relevant to a narrower regional request because it describes a cross-market event. Each event includes affected asset classes.

Date states:

| State | Meaning |
| --- | --- |
| `confirmed` | The saved publisher calendar states an exact day or meeting range |
| `tentative` | The publisher supplies dates but identifies the schedule as tentative |
| `window` | Evidence supports a range, such as late October, rather than one day |
| `watchlist` | No sourced date was verified in the requested window; start/end dates are null |

Watchlist membership never means the event will happen this month. Monthly or annual cadence is a research aid only. The agent must not infer a calendar date from it. A later capture can revise a schedule; already-submitted jobs keep their original versions.

The calendar parsers preserve source table headings, quotations, and raw captures. Their normalized text contains an `EVENTLENS_SCHEDULE_V1` section. Only these validated records, or the explicit next-meeting sentence in Fed minutes, create dated occurrences. Parser errors appear in refresh results. A calendar date does not establish that an event actually took place.

## Import an event calendar

Send a JSON object to `POST /v1/calendar`. Supply the usual source fields: `title`, `publisher`, HTTPS `url`, `published_at`, `document_date`, `markets`, `topics`, and the actual `text` (100–500,000 characters). Set `kind` to `calendar`, or omit it. Add `events`:

```json
[
  {
    "family_id": "cn_politburo",
    "name": "China Politburo policy meeting",
    "start_date": "2026-10-21",
    "end_date": "2026-10-31",
    "timezone": "Asia/Shanghai",
    "date_status": "window",
    "quotes": ["Copy an exact passage from the submitted source text."]
  }
]
```

This is a schema illustration, not an announcement of a meeting. Replace the dates and quote with supported values. An import checks literal source presence and field structure; the importing analyst remains responsible for the date interpretation. It does not fetch the URL. The receipt timestamp is set by the server. An invalid quote, unknown family, reversed dates, or invalid timezone rejects the import.

For a source already containing the normalized schedule section, `POST /v1/sources` accepts `kind: calendar` and performs the same validation. Avoid manually editing the normalized section; use the structured endpoint.

## Import research evidence

`POST /v1/sources` accepts these source types:

| Source kind | Use |
| --- | --- |
| `statement`, `minutes`, `economic_release`, `news` | Dated factual context |
| `market_expectations` | Current market expectations or consensus |
| `analyst_report` | Attributed analyst views |
| `market_history` | Documented market reactions to a previous event |

All sources require publication, context, and market metadata. Use catalog family IDs in `topics` to connect evidence to the relevant event. The corpus can contain reports in different languages, but word-overlap search is more reliable with exact terms from the source. The model can read any eligible document by source ID.

A historical-impact claim must cite `market_history` and use `context: historical`. An analyst-view claim must cite `analyst_report`. A current expectation must cite a current `market_expectations` source. A policy decision is not proof of a market reaction. A link to a research homepage is not a dated analyst view. Exact citations are necessary but do not prove economic relevance; claim review remains separate.

## Research and export

1. Refresh sources with `POST /v1/refresh`. The optional `providers` list selects `fed`, `ecb`, `usda`, `cftc`, `nbs`, `nyfed`, or `bls`.
2. Import any additional calendars and research evidence.
3. Submit `POST /v1/briefs` with the date window, `markets`, and `question`. `include_watchlist` defaults to `true`. Set `refresh_job_id` to preserve a completed refresh's provider status in the brief.
4. Download the Markdown brief and `calendar.csv` from the job. The CSV retains unselected candidates, source URLs, date uncertainty, research priority, supported historical impact, analyst views, and risk claims. Unresearched fields stay blank.
5. Review claims through the append-only review endpoint. A `partial` result has usable supported material alongside coverage or research gaps.

The NY Fed collector follows up to two published next-month links. It supplies US indicator dates independently of direct BLS access. Each month retains its own source URL and capture.

A refresh succeeds operationally if at least one provider supplies sources. Its result still lists every provider error. If all providers fail, the job fails. The request CLI saves this result as `refresh.json`; the report carries the linked failure summary. No result claims complete coverage just because a network request succeeded.

## Verification

The global regression suite exercises calendar layouts, holiday exceptions, exact versus uncertain dates, multi-market filtering, duplicate employment indicators, separate inflation releases, snapshot cutoffs, partial collector failure, CSV export, API defaults, and source-type enforcement. A scripted model test retrieves history and analyst views, submits an invalid citation type, receives feedback, and repairs the draft. That test verifies controller behavior, not live model quality.

The live service acceptance record is `reports/global-service-acceptance.json`. Its execution type identifies whether research used rules or a real provider. No internship workbook, employer source code, or private analyst report is included in the repository.
