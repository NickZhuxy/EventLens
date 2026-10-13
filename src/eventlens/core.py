"""Validated records, exact arithmetic, source identity, and immutable persistence."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from pathlib import Path
import json
import re
import sqlite3


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value):
    return sha256(value if isinstance(value, bytes) else value.encode()).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def timestamp(value):
    try:
        t = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("timestamp must be ISO 8601 with a timezone") from exc
    if t.tzinfo is None:
        raise ValueError("timestamp requires a timezone")
    return t


def number(value):
    if isinstance(value, bool) or value is None:
        raise ValueError("value must be a finite decimal")
    try:
        d = Decimal(str(value).replace(",", ""))
    except InvalidOperation as exc:
        raise ValueError("invalid decimal") from exc
    if not d.is_finite():
        raise ValueError("non-finite decimal")
    return d


@dataclass(frozen=True)
class Source:
    source_id: str
    issuer: str
    url: str
    published_at: str
    available_at: str
    retrieved_at: str
    reporting_period: str
    forecast_horizons: list[str]
    text: str
    content_hash: str
    snapshot_kind: str = "text"
    timestamp_precision: str = "day_conservative_end"

    def __post_init__(self):
        if not self.source_id or not re.fullmatch(r"[A-Z0-9.-]+", self.issuer):
            raise ValueError("invalid source identity")
        if not self.url.startswith("https://"):
            raise ValueError("source must retain an HTTPS original URL")
        times = [timestamp(x) for x in (self.published_at, self.available_at, self.retrieved_at)]
        if times[1] < times[0] or times[2] < times[1]:
            raise ValueError("source timestamps out of order")
        if not self.text.strip() or digest(self.text) != self.content_hash:
            raise ValueError("empty or hash-mismatched source")
        if not self.reporting_period or not self.forecast_horizons:
            raise ValueError("period metadata required")

    def eligible(self, cutoff, mode="disclosure"):
        boundary = timestamp(cutoff)
        if mode not in {"disclosure", "snapshot"}:
            raise ValueError("invalid cutoff mode")
        times = [self.published_at, self.available_at]
        if mode == "snapshot":
            times.append(self.retrieved_at)
        return all(timestamp(t) <= boundary for t in times)


def load_corpus(manifest_path):
    path = Path(manifest_path)
    manifest = json.loads(path.read_text())
    sources = {}
    for record in manifest["sources"]:
        meta = dict(record)
        text_path = (path.parent / meta.pop("path")).resolve()
        if not text_path.is_relative_to(path.parent.resolve()):
            raise ValueError("snapshot outside manifest directory")
        source = Source(text=text_path.read_text(), **meta)
        if source.source_id in sources:
            raise ValueError("duplicate source id in manifest")
        sources[source.source_id] = source
    return manifest, sources


UNITS = {"billion": Decimal(10)**9, "million": Decimal(10)**6,
         "USD": Decimal(1), "percent": Decimal(1)}


@dataclass(frozen=True)
class Metric:
    source_id: str
    issuer: str
    metric: str
    currency: str | None
    unit: str
    basis: str
    horizon: str
    calendar: str
    definition: str
    status: str
    lower: str | None
    upper: str | None
    evidence: str
    horizon_evidence: str

    def __post_init__(self):
        if self.metric not in {"revenue", "operating_margin"}:
            raise ValueError("unsupported metric")
        if self.basis not in {"reported", "GAAP", "non-GAAP", "unknown"}:
            raise ValueError("invalid basis")
        if self.calendar not in {"fiscal", "calendar"}:
            raise ValueError("invalid calendar")
        if not re.fullmatch(r"(?:FY|CY)20\d{2}(?:-Q[1-4])?", self.horizon):
            raise ValueError("invalid forecast horizon")
        if self.horizon.startswith("FY") != (self.calendar == "fiscal"):
            raise ValueError("calendar/horizon mismatch")
        if self.unit not in UNITS or self.status not in {"provided", "withdrawn", "missing"}:
            raise ValueError("invalid unit/status")
        if self.metric == "revenue" and (self.unit == "percent" or self.currency not in {"USD", "EUR", "GBP"}):
            raise ValueError("revenue requires currency and amount unit")
        if self.metric == "operating_margin" and (self.unit != "percent" or self.currency is not None):
            raise ValueError("margin requires percent and no currency")
        if self.status == "provided":
            if number(self.lower) > number(self.upper):
                raise ValueError("reversed range")
        elif self.lower is not None or self.upper is not None:
            raise ValueError("absent/withdrawn values must be null")
        if not self.definition:
            raise ValueError("definition required")

    @property
    def observation_id(self):
        return digest(canonical(asdict(self)))

    def bounds(self):
        return tuple(number(x) * UNITS[self.unit] for x in (self.lower, self.upper))


def compare(old: Metric | None, new: Metric | None):
    """Input observations must pass evidence validation before this function is used."""
    result = {"status": "insufficient_evidence", "reason": "missing_guidance", "calculation": None}
    if old is None or new is None:
        return result
    for field in ("issuer", "metric", "currency", "basis", "horizon", "calendar", "definition"):
        if getattr(old, field) != getattr(new, field):
            return {**result, "reason": "incompatible_" + field}
    if "unknown" in (old.basis, new.basis) or "unknown" in (old.definition, new.definition):
        return {**result, "reason": "unknown_definition_or_basis"}
    if new.status == "withdrawn":
        return {**result, "status": "supported", "reason": "guidance_withdrawn"}
    if old.status != "provided" or new.status != "provided":
        return {**result, "reason": "absent_or_previously_withdrawn_guidance"}
    a, b = old.bounds(), new.bounds()
    ma, mb = sum(a) / 2, sum(b) / 2
    dl, du = b[0] - a[0], b[1] - a[1]
    change = ("unchanged" if dl == du == 0 else "raised" if dl >= 0 and du >= 0
              else "lowered" if dl <= 0 and du <= 0 else "mixed_range")
    return {"status": "supported", "reason": change, "calculation": {
        "old_lower": str(a[0]), "old_upper": str(a[1]), "new_lower": str(b[0]), "new_upper": str(b[1]),
        "old_midpoint": str(ma), "new_midpoint": str(mb), "midpoint_delta": str(mb - ma),
        "lower_delta": str(dl), "upper_delta": str(du),
        "relative_midpoint_change_percent": None if ma == 0 else str((mb - ma) / abs(ma) * 100),
        "delta_unit": "percentage_points" if old.metric == "operating_margin" else old.currency,
        "range_change": change}}


class Store:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS sources (source_id TEXT PRIMARY KEY, content_hash TEXT NOT NULL, record TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, record TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS reviews (review_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, record TEXT NOT NULL);
        ''')

    def ingest(self, source):
        encoded = canonical(asdict(source))
        existing = self.db.execute("SELECT record FROM sources WHERE source_id=?", (source.source_id,)).fetchone()
        if existing:
            if existing[0] != encoded:
                raise ValueError("immutable source identity collision; use a new source_id for a revision")
            return False
        with self.db:
            self.db.execute("INSERT INTO sources VALUES (?,?,?)", (source.source_id, source.content_hash, encoded))
        return True

    def save_run(self, run):
        with self.db:
            self.db.execute("INSERT INTO runs VALUES (?,?,?)", (run["run_id"], now(), canonical(run)))

    def save_review(self, review):
        with self.db:
            self.db.execute("INSERT INTO reviews VALUES (?,?,?)", (digest(canonical(review)), now(), canonical(review)))

    def close(self):
        self.db.close()
