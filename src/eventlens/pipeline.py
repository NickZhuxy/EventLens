"""One pair through extraction, validation, arithmetic, and an auditable trace."""
from __future__ import annotations
from dataclasses import asdict
import time
from uuid import uuid4
from .core import compare, now, canonical, digest, timestamp
from .extraction import extract, validate_evidence, explanation_candidates, explanation_status
from .retrieval import ReadTools


def run_pair(sources, case, method="A", adapter=None, config=None, cutoff_mode="disclosure"):
    start = time.perf_counter()
    cfg = config or {}
    run = {"run_id": str(uuid4()), "created_at": now(), "case": case, "method": method,
           "config": cfg, "cutoff_mode": cutoff_mode, "trace": [], "extractions": [],
           "explanations": [], "errors": [], "calls": 0, "tokens": None,
           "label_status": "not_used_by_system", "human_semantic_review": "pending"}
    selected = [sources[s] for s in (case["old"], case["new"])]
    run["source_hashes"] = {s.source_id: s.content_hash for s in selected}
    run["input_hash"] = digest(canonical({"case": case, "sources": run["source_hashes"]}))
    metrics = []
    if selected[0].issuer != selected[1].issuer or selected[0].issuer != case["issuer"]:
        run["errors"].append("issuer_mismatch")
    if timestamp(selected[0].available_at) >= timestamp(selected[1].available_at):
        run["errors"].append("stale_or_reversed_disclosure_pair")
    if any(not s.eligible(case["cutoff"], cutoff_mode) for s in selected):
        run["errors"].append("source_after_cutoff")
    if run["errors"]:
        result = {"status": "insufficient_evidence", "reason": run["errors"][0], "calculation": None}
    else:
        if method == "A":
            run["model"] = None
            run["execution_kind"] = "deterministic"
            run["context_characters"] = sum(len(s.text) for s in selected)
            for source in selected:
                metric, issues = extract(source, case["horizon"])
                run["trace"].append({"stage": "rule_extraction", "source_id": source.source_id, "issues": issues})
                metrics.append(metric)
                run["explanations"].extend(explanation_candidates(source))
        elif method == "D":
            from .document_diff import extract_pair
            run["model"] = None
            run["execution_kind"] = "deterministic"
            run["context_characters"] = sum(len(s.text) for s in selected)
            metrics = extract_pair(*selected, case["horizon"], run)
        elif method in {"B", "C"}:
            from .llm import model_extract
            metrics = model_extract(selected, sources, case, method, adapter, cfg, run, cutoff_mode)
        else:
            raise ValueError("method must be A, B, C, or D")
        valid = []
        for source, metric in zip(selected, metrics):
            if metric:
                validation = validate_evidence(metric, source)
                if metric.horizon != case["horizon"]:
                    validation["errors"].append("question_horizon_mismatch")
                    validation["semantic_screen"] = "fail"
                if metric.metric != case.get("metric", "revenue"):
                    validation["errors"].append("question_metric_mismatch")
                    validation["semantic_screen"] = "fail"
                run["extractions"].append({"metric": asdict(metric), "validation": validation})
                valid.append(metric if not validation["errors"] else None)
            else:
                valid.append(None)
        result = compare(*valid) if len(valid) == 2 else {"status": "insufficient_evidence", "reason": "model_output_invalid", "calculation": None}
        if any("conflicting_guidance_ranges" in t.get("issues", []) for t in run["trace"]):
            result = {"status": "conflicting", "reason": "conflicting_guidance_ranges", "calculation": None}
    run["comparison"] = result
    run["explanation_conclusion"] = explanation_status(run["explanations"])
    run["conclusion"] = ("conflicting" if run["explanation_conclusion"]["status"] == "conflicting" else result["status"])
    run["trace"].append({"stage": "deterministic_comparison", "result": result})
    run["latency_ms"] = round((time.perf_counter() - start) * 1000, 3)
    return run
