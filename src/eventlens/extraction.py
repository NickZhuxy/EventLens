"""Deliberately small rule baseline; it abstains on unsupported table layouts."""
from __future__ import annotations
from dataclasses import asdict
import re
from .core import Metric, number

# Bounded lexical patterns, not a general financial-table parser.
RANGE = re.compile(r"\$\s*(?P<low>\d[\d,]*(?:\.\d+)?)\s*(?P<u1>billion|million)?\s*(?:to|[-–—])\s*\$?\s*(?P<high>\d[\d,]*(?:\.\d+)?)\s*(?P<u2>billion|million)?", re.I)
HORIZON = re.compile(r"\b(?:fiscal\s+(?:year\s+)?(?P<long>20\d{2})|FY\s*(?P<short>\d{2}|20\d{2}))\b", re.I)
QUARTER = re.compile(r"\b(?:first|second|third|fourth|1st|2nd|3rd|4th)\s+quarter\b|\bQ[1-4]\b", re.I)
METRIC_ROW = re.compile(r"^\s*(?:Total\s+)?Revenue\b", re.I)


def horizons(text):
    found = []
    for m in HORIZON.finditer(text):
        year = m.group("long") or m.group("short")
        found.append(("FY" + ("20" + year if len(year) == 2 else year), m.start(), m.end()))
    return found


def extract(source, horizon):
    """Only annual total-revenue ranges with one unambiguous nearby heading."""
    lines = source.text.splitlines(keepends=True)
    candidates, issues = [], []
    offset = 0
    for line in lines:
        end = offset + len(line.rstrip("\n"))
        if METRIC_ROW.match(line):
            matches = list(RANGE.finditer(line))
            context = source.text[max(0, offset - 900):offset]
            hs = horizons(context)
            if matches and hs:
                h, pos, _ = hs[-1]
                # Heading starts at its line. A quarter-specific heading is not annual guidance.
                start = context.rfind("\n", 0, pos) + 1
                heading = context[start:]
                if h == horizon and not QUARTER.search(heading):
                    if len(matches) != 1:
                        issues.append("ambiguous_multi_column_revenue_row")
                    else:
                        m = matches[0]
                        u1, u2 = m.group("u1"), m.group("u2")
                        unit = (u2 or u1 or ("million" if re.search(r"in millions", line, re.I) else "")).lower()
                        if u1 and u2 and u1.lower() != u2.lower():
                            issues.append("mixed_units_within_range")
                        elif unit:
                            hstart = max(0, offset - 900) + start
                            evidence = source.text[offset:end]
                            candidates.append(Metric(source.source_id, source.issuer, "revenue", "USD", unit,
                                "reported", horizon, "fiscal", "total_revenue_as_reported", "provided",
                                str(number(m.group("low"))), str(number(m.group("high"))), evidence,
                                source.text[hstart:end]))
        offset += len(line)
    unique = {}
    for m in candidates:
        unique[(m.lower, m.upper, m.unit, m.horizon)] = m
    if len(unique) > 1:
        return None, issues + ["conflicting_guidance_ranges"]
    if not unique:
        return None, issues + ["no_unambiguous_annual_revenue_range"]
    return next(iter(unique.values())), issues


def validate_evidence(metric, source):
    """Literal check plus conservative semantic screen; human review is still required.

    The independent screen prevents obvious quote laundering (wrong numbers, metric,
    time frame, or unit). It is not a general entailment oracle.
    """
    errors = []
    if metric.source_id != source.source_id or metric.issuer != source.issuer:
        errors.append("wrong_source_or_issuer")
    for name in ("evidence", "horizon_evidence"):
        quote = getattr(metric, name)
        if not quote or quote not in source.text:
            errors.append("nonliteral_" + name)
    if metric.horizon not in source.forecast_horizons:
        errors.append("horizon_not_in_source_metadata")
    if metric.evidence not in metric.horizon_evidence:
        errors.append("disconnected_horizon_evidence")
    if metric.status == "missing":
        errors.append("missing_is_abstention_not_extraction")
    elif metric.status == "withdrawn":
        if not re.search(r"withdraw|suspend|no longer provid", metric.evidence, re.I):
            errors.append("withdrawal_not_supported")
    else:
        nums = {number(n) for n in re.findall(r"(?<![\w])\d[\d,]*(?:\.\d+)?", metric.evidence)}
        if not {number(metric.lower), number(metric.upper)} <= nums:
            errors.append("value_not_in_quote")
        if metric.unit in {"million", "billion"} and metric.unit not in metric.evidence.lower():
            errors.append("unit_not_in_quote")
        if metric.unit == "percent" and not re.search(r"%|percent", metric.evidence):
            errors.append("unit_not_in_quote")
        if metric.currency == "USD" and not re.search(r"\$|USD|U.S. dollars", metric.evidence):
            errors.append("currency_not_in_quote")
    term = "revenue" if metric.metric == "revenue" else "operating margin"
    if term not in metric.evidence.lower():
        errors.append("metric_not_in_quote")
    # Keep annual/quarter distinction separate from a raw FY substring match.
    hs = horizons(metric.horizon_evidence)
    if not hs or hs[-1][0] != metric.horizon:
        errors.append("horizon_not_supported")
    if QUARTER.search(metric.horizon_evidence):
        errors.append("quarterly_or_ambiguous_horizon")
    if metric.basis in {"GAAP", "non-GAAP"}:
        if metric.basis not in metric.evidence:
            errors.append("basis_not_in_quote")
    return {"literal_valid": not any(x.startswith("nonliteral") for x in errors),
            "semantic_screen": "pass" if not errors else "fail", "errors": errors,
            "human_semantic_review": "pending", "observation_id": metric.observation_id}


def explanation_candidates(source):
    """Return exact source statements, never inferred causal decompositions."""
    out = []
    for line in source.text.splitlines():
        if len(line) <= 1800 and re.search(r"rais|lower|revis", line, re.I) and re.search(r"target|guidance|outlook", line, re.I):
            if re.search(r"given|driv|drov|caus|explai|strength|result of|because|due to", line, re.I):
                out.append({"source_id": source.source_id, "quote": line,
                            "type": "management_statement_candidate", "semantic_review": "pending"})
    return out[:5]


def explanation_status(claims):
    """Contradiction is a review signal, not a resolution of managerial causality."""
    # Explicit opposing assertions on the same named driver only; uncertainty remains otherwise.
    for driver in ("demand", "currency", "pricing", "volume"):
        positive, negative = [], []
        for c in claims:
            q = c["quote"].lower()
            if re.search(rf"\b{driver}\b", q):
                if re.search(rf"{driver} (?:did not|was not|is not)", q):
                    negative.append(c)
                elif re.search(rf"{driver} (?:drove|caused|explains)", q):
                    positive.append(c)
        if positive and negative:
            return {"status": "conflicting", "reason": "opposing_explicit_" + driver + "_statements"}
    return {"status": "insufficient_evidence", "reason": "semantic_review_required" if claims else "no_explicit_explanation_found"}
