"""Pair-scoped, cutoff-enforced read-only tools; no network or filesystem arguments."""
from __future__ import annotations
import re


class ReadTools:
    def __init__(self, sources, allowed_ids, cutoff, mode="disclosure", max_chars=6000):
        self.sources = {sid: sources[sid] for sid in allowed_ids
                        if sid in sources and sources[sid].eligible(cutoff, mode)}
        self.max_chars = max_chars

    def execute(self, name, arguments):
        if not isinstance(arguments, dict):
            raise ValueError("tool arguments must be an object")
        if name == "search_passages":
            if set(arguments) != {"source_id", "query"}:
                raise ValueError("search requires source_id and query only")
            sid, query = arguments["source_id"], arguments["query"]
            if not isinstance(query, str) or not 1 <= len(query) <= 300:
                raise ValueError("query must be 1..300 characters")
            src = self._source(sid)
            terms = set(re.findall(r"\w+", query.lower()))
            candidates = []
            # Overlapping literal windows preserve table headings and exact offsets.
            for start in range(0, len(src.text), 700):
                end = min(start + 1400, len(src.text))
                quote = src.text[start:end]
                score = sum(1 for t in terms if t in quote.lower())
                if score:
                    candidates.append({"source_id": sid, "start": start, "end": end,
                                       "score": score, "quote": quote})
            candidates.sort(key=lambda p: (-p["score"], p["start"]))
            return {"passages": candidates[:3]}
        if name == "get_source":
            if set(arguments) != {"source_id", "start", "end"}:
                raise ValueError("get_source requires source_id, start, end only")
            src = self._source(arguments["source_id"])
            start, end = arguments["start"], arguments["end"]
            if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(src.text):
                raise ValueError("invalid character offsets")
            if end - start > self.max_chars:
                raise ValueError("source request exceeds context budget")
            return {"source_id": src.source_id, "start": start, "end": end, "quote": src.text[start:end]}
        raise ValueError("unknown read-only tool")

    def _source(self, source_id):
        if not isinstance(source_id, str) or source_id not in self.sources:
            raise ValueError("source outside allowed pair/cutoff")
        return self.sources[source_id]
