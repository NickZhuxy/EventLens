# EventLens service operations

This deployment runs on one host. FastAPI accepts requests; a separate worker executes them. Both use a local SQLite database on the named Docker volume. Keep the volume on local disk, not an NFS share. The API and worker use the same image and configuration.

## Configuration

| Setting | Use |
| --- | --- |
| `EVENTLENS_SERVICE_TOKEN` | Required bearer token, at least 24 characters; separate from the model key |
| `EVENTLENS_API_KEY` | Provider key, needed for `agent` and `single` jobs |
| `EVENTLENS_MODEL` | Explicit model identifier; clients cannot override it |
| `EVENTLENS_BASE_URL` | HTTPS base URL; `.env.example` selects `https://api.deepseek.com` |
| `EVENTLENS_REASONING_EFFORT` | DeepSeek only: `none`, `low`, `high`, or `max`; default `low` |
| `EVENTLENS_PORT` | Host port used by Compose; default `8000` |
| `EVENTLENS_MAX_PENDING_JOBS` | Queue capacity, default `50` |
| `EVENTLENS_STATE_DIR` | Native-process state directory; Compose fixes it at `/var/lib/eventlens` |
| `EVENTLENS_CONFIG` | Optional path to a JSON budget configuration inside the runtime |

The supplied configuration selects `deepseek-flash` with low reasoning effort. Create a key in the [DeepSeek console](https://platform.deepseek.com/api_keys), ensure the account has API credit, and save the key as `EVENTLENS_API_KEY` in the ignored `.env` file. Do not put the key in a request body or commit it. Recreate both containers with `docker compose up -d` after changing the environment file.

For the official DeepSeek endpoint, the adapter sends `max_tokens`, `response_format: {"type": "json_object"}`, and an explicit `thinking` setting. `low`, `high`, and `max` enable thinking; `none` disables it. The default output budget is 6,000 tokens per call, including reasoning output. EventLens uses JSON research actions instead of the native `tools` parameter. See the [DeepSeek request reference](https://api-docs.deepseek.com/api/create-chat-completion/) and [thinking guide](https://api-docs.deepseek.com/guides/thinking_mode/).

Other endpoints retain the existing Chat Completions request format: `max_completion_tokens`, JSON-object responses, and `store: false`. To use one, change the model, key, and base URL together and remove `EVENTLENS_REASONING_EFFORT`. Without an endpoint environment setting, the lower-level client retains `https://api.openai.com/v1` for compatibility. Provider-specific fallback keys are restricted to their official HTTPS hosts: `DEEPSEEK_API_KEY` for DeepSeek and `OPENAI_API_KEY` for OpenAI. A custom endpoint requires `EVENTLENS_API_KEY`.

Each queued model job saves its model, base URL, reasoning effort, and budgets. API clients cannot override these server settings. The worker uses the saved reasoning effort even if the default later changes. If its endpoint differs from the saved endpoint, it fails the job before sending a credential. Check or resubmit that job after restoring the intended configuration. Credentials are loaded only from the worker environment and are never part of the saved settings.

The provider adapter allows two retries for connection failures, HTTP 408/429, and selected 5xx errors. Each attempt has a 30-second socket timeout. It does not retry authentication errors or malformed JSON. Successful calls retain transport attempt counts in the trace. A retry may incur provider cost when the previous response was lost. A worker crash therefore never triggers automatic job replay. See the provider's [error guidance](https://developers.openai.com/api/docs/guides/error-codes).

For a native loopback model server, set `EVENTLENS_ALLOW_LOCAL_HTTP=1` and use `http://127.0.0.1:PORT/v1`. Set a nonempty local key value if that server does not require a key. This exception is restricted to loopback addresses; a remote model endpoint requires HTTPS.

## Starting and checking the service

```sh
docker compose up --build -d
docker compose ps
docker compose logs --tail 50 api worker
curl --fail http://127.0.0.1:8000/health/ready
```

`/health/live` checks the API process. `/health/ready` also requires a worker heartbeat in the last 30 seconds. Readiness is an infrastructure check; `/v1/status` reports whether the API has model settings and credentials. A model job still fails if the provider rejects the credentials or model.

The API and worker run as UID 10001. The image excludes `.env`, local state, research reports, and internship material. Compose uses a read-only root filesystem, drops Linux capabilities, and sets CPU and memory limits. The database volume is the writable application state.

This uses the separate-process container pattern described in the [FastAPI deployment guide](https://fastapi.tiangolo.com/deployment/docker/). The Python base image and service dependency versions are recorded in the build inputs.

For access from another machine, place an HTTPS reverse proxy in front of the loopback port. Keep the bearer token in a secret store or the host's protected environment file. This release uses one shared service token, so it is suitable for a personal instance or a small trusted analyst group, not separate tenant accounts.

## API examples

Load the trusted local configuration into your shell:

```sh
set -a
. ./.env
set +a
```

Queue a source refresh:

```sh
curl --fail-with-body http://127.0.0.1:8000/v1/refresh \
  -H "Authorization: Bearer $EVENTLENS_SERVICE_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"limit":8}'
```

The response includes `id`, `status`, and the saved request. Poll `GET /v1/jobs/{id}` until `succeeded` or `failed`. A refresh with at least one successful source has `status: succeeded`; its result lists provider-level successes and errors. If all providers fail, the job has `status: failed` and `error: source_refresh_incomplete`. Successful imports remain available. Pass the refresh job ID as `refresh_job_id` when submitting a brief to retain this coverage status.

Use the CLI for a current window:

```sh
eventlens-service request --refresh --days 31 --out work/current-brief
```

Or submit a custom request. Dates below illustrate the fields; choose a cutoff after your source refresh and a window starting on or after that cutoff's New York date.

```json
{
  "as_of": "2026-10-08T12:00:00Z",
  "start_date": "2026-10-08",
  "end_date": "2026-11-07",
  "markets": ["CN", "HK", "TW", "SEA", "EU", "US", "JP", "GLOBAL"],
  "method": "agent",
  "cutoff_mode": "snapshot",
  "question": "Summarize upcoming policy events and possible liquidity or volatility effects."
}
```

Send this body to `POST /v1/briefs`. Optional `source_ids` fixes an explicit selection of up to 100 stored source versions. With no selection, the API uses the latest eligible version of each URL at submission time. The saved job fixes those IDs and the model configuration. The worker rechecks the cutoff before model access.

`Idempotency-Key` accepts a caller-chosen string of 1–128 ASCII characters with no spaces. Repeating the same request and key returns the original job, including after a source refresh or service restart. A different body with the same key returns HTTP 409. A full queue returns HTTP 429. Keep the returned job ID if a client wait times out: the server continues the job.

Import an additional source through `POST /v1/sources`:

```json
{
  "title": "Dated market consensus note",
  "publisher": "Your licensed research source",
  "url": "https://example.com/research/note",
  "published_at": "2026-10-08T10:00:00Z",
  "document_date": "2026-10-08",
  "kind": "market_expectations",
  "markets": ["US", "GLOBAL"],
  "topics": ["fomc"],
  "text": "Paste the actual source text here. The import requires at least 100 characters."
}
```

The example is a schema illustration, not research evidence. Import only text you can use. The service records the receipt time itself and labels publication metadata as supplied by the importing analyst. It never fetches the URL in a manual import. Changes create a new source version. Reimporting the same version preserves its first receipt time.

After a run, each `result.review_queue` item has an `observation_id`. Submit an analyst decision to `POST /v1/jobs/{id}/reviews`:

```json
{
  "observation_id": "COPY_THE_OBSERVATION_ID",
  "decision": "supports",
  "reviewer": "Analyst name",
  "note": "Explain the evidence checked and any qualification."
}
```

Decisions are `supports`, `reject`, or `uncertain`. Reviews append to history. They do not rewrite the source, raw draft, or earlier decisions.

## Source collection

The collector reads the [Federal Reserve monetary-policy RSS feed](https://www.federalreserve.gov/feeds/press_monetary.xml). It selects FOMC statements and minutes notices. For a minutes notice, it follows the exact HTML minutes link and uses the notice's release timestamp rather than the meeting date. It saves the feed item, captured HTML, hashes, normalized article text, and retrieval time in the database.

The other collectors read official ECB, USDA, CFTC, NBS, NY Fed, and BLS calendars. See [global workflow](global-workflow.md) for source coverage and structured imports. Collection is restricted to allowlisted official URLs, including on redirects. Responses have a size limit and timeout. A changed page structure or blocked response appears as a refresh error. It is not replaced with invented text.

Refresh is explicit: use `POST /v1/refresh` or the request client's `--refresh` flag. The service does not install a background collection schedule. An existing scheduler can call the authenticated refresh endpoint when needed.

## Failure and recovery

Jobs move from `queued` to `running`, then to `succeeded` or `failed`. Research outcomes are separate: `ready_for_review`, `partial`, `insufficient_evidence`, or `failed`. A completed job with insufficient evidence is a valid execution with no supported brief.

A worker updates its heartbeat every five seconds. Another worker marks an abandoned active job as `worker_interrupted` after 60 seconds. Queued jobs remain available. Read the failed job before submitting a replacement with a new idempotency key. The previous run may have reached the model provider.

On SIGTERM, the worker stops accepting new work. It lets the current provider attempt finish, then stops before another model action. Compose allows 120 seconds before a forced stop. A source refresh can exceed that interval on a slow network; successfully committed sources remain stored and its abandoned job is recovered by the same lease rule.

To restart services without deleting data:

```sh
docker compose restart
```

To stop them and retain the volume:

```sh
docker compose down
```

## Backup and restore

SQLite's online backup API captures committed data, including WAL contents. Use it while the service is running:

```sh
mkdir -p work/backups
docker compose exec -T api python -c 'import sqlite3; a=sqlite3.connect("/var/lib/eventlens/service.sqlite"); b=sqlite3.connect("/tmp/backup.sqlite"); a.backup(b); b.close(); a.close()'
docker compose cp api:/tmp/backup.sqlite work/backups/service.sqlite
```

For restore, stop the worker and API first. Restore into a clean state directory with UID 10001 ownership, then restart both containers. Do not combine a restored main database with old `-wal` or `-shm` files. Keep the original volume until the restored instance passes health and job-history checks.

## Acceptance checks

```sh
python -m pip install -c deploy/requirements.lock '.[service,test]'
python -m unittest discover -s tests -v
python scripts/service_smoke.py
python scripts/service_smoke.py --url http://127.0.0.1:8000 --refresh --live
```

The first HTTP check starts native processes against a temporary database and uses saved public sources with the rule method. The final command checks the deployed service using current sources and the real configured model. It makes paid model calls and records an `uncertain` review marked as an automated persistence check. It does not mark claims as human-approved.

The runtime can operate without the historical fixture files. The container acceptance check uses sources fetched at runtime. The live LLM acceptance result must be reported separately from rule-based infrastructure acceptance.
