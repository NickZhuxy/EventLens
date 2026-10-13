"""Authenticated job and evidence API. Execution happens in a separate worker."""
import hmac
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field

from .. import __version__
from ..core import now
from ..macro.records import validate_case
from ..macro.catalog import MARKETS, catalog
from ..macro.schedules import encode_schedule, decode_schedule
from .providers import PROVIDERS
from .ingestion import make_source
from .settings import Settings
from .store import Conflict, Database, QueueFull


class Body(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True, strict=True)


class BriefRequest(Body):
    as_of: str = Field(max_length=40)
    start_date: str = Field(max_length=10)
    end_date: str = Field(max_length=10)
    question: str = Field(default='Prepare an evidence-linked macro-event risk brief.', min_length=1, max_length=1000)
    method: Literal['agent', 'single', 'rules'] = 'agent'
    cutoff_mode: Literal['snapshot', 'publication'] = 'snapshot'
    markets: list[str] = Field(default_factory=lambda: list(MARKETS), min_length=1, max_length=8)
    include_watchlist: bool = True
    refresh_job_id: str | None = Field(default=None, max_length=40)
    source_ids: list[str] | None = Field(default=None, min_length=1, max_length=100)


class SourceImport(Body):
    title: str = Field(min_length=1, max_length=300)
    publisher: str = Field(min_length=1, max_length=200)
    url: str = Field(min_length=1, max_length=2000)
    published_at: str = Field(max_length=40)
    available_at: str | None = Field(default=None, max_length=40)
    document_date: str = Field(max_length=10)
    kind: Literal['statement', 'minutes', 'market_expectations', 'economic_release', 'analyst_report', 'market_history', 'news', 'calendar']
    markets: list[str] = Field(default_factory=lambda: ['US'], min_length=1, max_length=8)
    text: str = Field(min_length=100, max_length=500000)
    topics: list[str] = Field(default_factory=lambda: ['monetary_policy'], min_length=1, max_length=20)


class CalendarImport(SourceImport):
    kind: Literal['calendar'] = 'calendar'
    events: list[dict] = Field(min_length=1, max_length=500)


class RefreshRequest(Body):
    providers: list[Literal['fed', 'ecb', 'usda', 'cftc', 'nbs', 'nyfed', 'bls']] = Field(default_factory=lambda: list(PROVIDERS), min_length=1, max_length=7)
    limit: int = Field(default=8, ge=1, le=20)


class ReviewRequest(Body):
    observation_id: str = Field(pattern=r'^[a-f0-9]{64}$')
    decision: Literal['supports', 'reject', 'uncertain']
    reviewer: str = Field(min_length=1, max_length=100)
    note: str = Field(min_length=1, max_length=4000)


def create_app(settings=None):
    settings = settings or Settings.from_env()
    db = Database(settings.database)
    app = FastAPI(title='EventLens', version=__version__, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.database = db
    auth = HTTPBearer(auto_error=False)

    def authorize(credentials: HTTPAuthorizationCredentials | None = Depends(auth)):
        if not credentials or not hmac.compare_digest(credentials.credentials.encode(), settings.api_token.encode()):
            raise HTTPException(401, 'Bearer token required', headers={'WWW-Authenticate': 'Bearer'})

    @app.exception_handler(RequestValidationError)
    async def invalid_body(request, exc):
        # Do not echo submitted document text or accidentally supplied credentials.
        return JSONResponse(status_code=422, content={'detail': [
            {'loc': e['loc'], 'msg': e['msg'], 'type': e['type']} for e in exc.errors()]})

    @app.middleware('http')
    async def bounded_body(request: Request, call_next):
        # The limit applies to chunked requests too, before JSON parsing.
        if request.method in {'POST', 'PUT', 'PATCH'}:
            size, chunks = 0, []
            async for chunk in request.stream():
                size += len(chunk)
                if size > 2_000_000:
                    return JSONResponse(status_code=413, content={'detail': 'request exceeds 2 MB'})
                chunks.append(chunk)
            request._body = b''.join(chunks)
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    @app.exception_handler(Conflict)
    async def conflict(request, exc):
        return JSONResponse(status_code=409, content={'detail': str(exc)})

    @app.exception_handler(QueueFull)
    async def full(request, exc):
        return JSONResponse(status_code=429, content={'detail': str(exc)}, headers={'Retry-After': '10'})

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse(status_code=422, content={'detail': str(exc)})

    @app.exception_handler(KeyError)
    async def missing(request, exc):
        return JSONResponse(status_code=404, content={'detail': 'record not found'})

    @app.get('/health/live')
    def live():
        return {'status': 'ok', 'version': __version__}

    @app.get('/health/ready')
    def ready():
        health = db.health()
        ok = health['workers'] > 0
        return JSONResponse(status_code=200 if ok else 503,
                            content={'status': 'ready' if ok else 'worker_unavailable'})

    dependencies = [Depends(authorize)]

    @app.get('/openapi.json', dependencies=dependencies)
    def openapi():
        return app.openapi()

    @app.get('/v1/status', dependencies=dependencies)
    def status():
        return {**db.health(), 'model': settings.model or None,
                'model_configured': bool(settings.model and settings.provider.credential()),
                'provider': settings.provider.provider, 'provider_config': settings.provider.to_dict(),
                'budgets': settings.config}

    @app.get('/v1/catalog', dependencies=dependencies)
    def coverage_catalog():
        return {'markets': list(MARKETS), 'families': catalog(), 'providers': list(PROVIDERS),
                'priority_basis': 'Research defaults; not measured historical volatility',
                'reference_basis': 'Discovery links; not dated claim evidence'}

    @app.post('/v1/calendar', dependencies=dependencies, status_code=201)
    def import_calendar(body: CalendarImport):
        data = body.model_dump()
        records = data.pop('events')
        data['text'] = encode_schedule(data['text'], records)
        value = make_source(**data)
        added = db.add_source(value, {'method':'analyst-calendar-import', 'timestamp_basis':'analyst-supplied publication',
                                     'validation':'literal quotes and schema; date interpretation requires analyst review'})
        return {'source_id':value.source_id, 'added':added, 'occurrences':len(records)}

    @app.get('/v1/sources', dependencies=dependencies)
    def sources(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
        values = list(db.sources().values())
        return {'total': len(values), 'sources': [s.metadata(now()) for s in values[offset:offset+limit]]}

    @app.get('/v1/sources/{source_id}', dependencies=dependencies)
    def source(source_id: str):
        return db.source_details(source_id)

    @app.post('/v1/sources', dependencies=dependencies, status_code=201)
    def import_source(body: SourceImport):
        value = make_source(**body.model_dump())
        if value.kind == 'calendar':
            decode_schedule(value)
        added = db.add_source(value, {'method': 'analyst-text-import', 'timestamp_basis': 'publication supplied by importing analyst'})
        return {'source_id': value.source_id, 'added': added, 'content_hash': value.content_hash}

    def submit(kind, request, key, identity):
        if key is not None and (not 1 <= len(key) <= 128 or not key.isascii() or any(c.isspace() for c in key)):
            raise ValueError('Idempotency-Key must contain 1..128 ASCII characters without spaces')
        job = db.submit(kind, request, key, settings.max_pending_jobs, identity=identity)
        return JSONResponse(status_code=202, content=job, headers={'Location': '/v1/jobs/'+job['id']})

    @app.post('/v1/refresh', dependencies=dependencies, status_code=202)
    def refresh(body: RefreshRequest, idempotency_key: str | None = Header(default=None)):
        return submit('refresh', body.model_dump(), idempotency_key, body.model_dump())

    @app.post('/v1/briefs', dependencies=dependencies, status_code=202)
    def brief(body: BriefRequest, idempotency_key: str | None = Header(default=None)):
        existing = db.replay('brief', body.model_dump(), idempotency_key)
        if existing:
            return JSONResponse(status_code=202, content=existing, headers={'Location': '/v1/jobs/'+existing['id']})
        case = dict(case_id='service-window', as_of=body.as_of, start_date=body.start_date,
                    end_date=body.end_date, question=body.question, markets=body.markets, split='custom')
        validate_case(case)
        if body.method != 'rules' and not (settings.model and settings.provider.credential()):
            raise HTTPException(503, 'Set EVENTLENS_MODEL and EVENTLENS_API_KEY before submitting model jobs')
        selected = db.sources(body.source_ids)
        if body.source_ids is None:
            # Choose the latest eligible version of each URL; preserve explicit selections as given.
            latest = {}
            for value in selected.values():
                if value.eligible(body.as_of, body.cutoff_mode):
                    previous = latest.get(value.url)
                    if previous is None or value.retrieved_at > previous.retrieved_at:
                        latest[value.url] = value
            selected = {s.source_id: s for s in latest.values()}
        if len(selected) > 100:
            raise ValueError('select at most 100 source versions for one briefing')
        collection_report = {}
        if body.refresh_job_id:
            refresh_job = db.get(body.refresh_job_id)
            if refresh_job['kind'] != 'refresh' or refresh_job['status'] not in {'succeeded', 'failed'}:
                raise ValueError('refresh_job_id must identify a completed refresh')
            refreshed = refresh_job['result'] or {}
            collection_report = {k:refreshed.get(k, {}) for k in ('providers', 'errors', 'retrieved_at')}
        request = dict(collection_report=collection_report, case=case, method=body.method, cutoff_mode=body.cutoff_mode,
                       source_ids=sorted(selected), include_watchlist=body.include_watchlist,
                       provider_config=settings.provider.to_dict(), config={**settings.config, 'model': settings.model})
        return submit('brief', request, idempotency_key, body.model_dump())

    @app.get('/v1/jobs', dependencies=dependencies)
    def jobs(limit: int = Query(50, ge=1, le=100)):
        return db.jobs(limit)

    @app.get('/v1/jobs/{job_id}', dependencies=dependencies)
    def job(job_id: str):
        return db.get(job_id)

    @app.get('/v1/jobs/{job_id}/brief', dependencies=dependencies, response_class=PlainTextResponse)
    def markdown(job_id: str):
        result = db.get(job_id)['result']
        if not result or 'brief_markdown' not in result:
            raise HTTPException(409, 'brief is not available for this job')
        return PlainTextResponse(result['brief_markdown'], media_type='text/markdown')

    @app.get('/v1/jobs/{job_id}/calendar.csv', dependencies=dependencies, response_class=PlainTextResponse)
    def calendar_csv(job_id: str):
        result = db.get(job_id)['result']
        if not result or 'calendar_csv' not in result:
            raise HTTPException(409, 'calendar is not available for this job')
        return PlainTextResponse('\ufeff'+result['calendar_csv'], media_type='text/csv',
                                 headers={'Content-Disposition':'attachment; filename=eventlens-calendar.csv'})

    @app.post('/v1/jobs/{job_id}/reviews', dependencies=dependencies, status_code=201)
    def review(job_id: str, body: ReviewRequest):
        return db.review(job_id, **body.model_dump())

    @app.get('/v1/jobs/{job_id}/reviews', dependencies=dependencies)
    def reviews(job_id: str):
        db.get(job_id)
        return db.reviews(job_id)

    return app
