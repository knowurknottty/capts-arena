from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CANONICAL_DIMENSIONS = (
    "answer_correctness",
    "stale_rejection",
    "contradiction_preservation",
    "citation_accuracy",
    "source_grounding",
)

DIMENSION_ALIASES: dict[str, tuple[str, ...]] = {
    "answer_correctness": ("answer_correctness", "correctness", "accuracy", "task_success"),
    "stale_rejection": ("stale_rejection", "staleness_handling", "freshness_handling"),
    "contradiction_preservation": ("contradiction_preservation", "contradiction_handling", "contradiction_integrity"),
    "citation_accuracy": ("citation_accuracy", "evidence_linking", "citation_integrity"),
    "source_grounding": ("source_grounding", "retrieval", "provenance", "grounding"),
}

FAILURE_COUNT_KEYS = (
    "unsupported_claims",
    "hallucinated_sources",
    "stale_memory_uses",
    "contradiction_collapses",
    "governance_violations",
    "bad_source_spans",
    "tool_use_failures",
)

FAILURE_TYPE_TO_COUNT = {
    "unsupported_claim": "unsupported_claims",
    "hallucinated_source": "hallucinated_sources",
    "stale_memory_used": "stale_memory_uses",
    "contradiction_collapsed": "contradiction_collapses",
    "governance_violation": "governance_violations",
    "bad_source_span": "bad_source_spans",
    "tool_use_failure": "tool_use_failures",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: str | Path, value: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_score_reports(path: str | Path) -> list[dict[str, Any]]:
    data = load_json(path)
    if isinstance(data, list):
        return [normalize_score_report(item) for item in data]
    if isinstance(data, dict) and isinstance(data.get("reports"), list):
        defaults = {
            "candidate_id": data.get("candidate_id"),
            "benchmark": data.get("benchmark") or data.get("benchmark_suite"),
            "scoring_version": data.get("scoring_version"),
        }
        return [normalize_score_report(item, **defaults) for item in data["reports"]]
    if isinstance(data, dict):
        return [normalize_score_report(data)]
    raise ValueError(f"Unsupported score report shape in {path!s}")


def normalize_score_report(
    raw: dict[str, Any],
    *,
    candidate_id: str | None = None,
    benchmark: str | None = None,
    scoring_version: str | None = None,
) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise TypeError("score report must be a JSON object")

    scores = raw.get("scores") if isinstance(raw.get("scores"), dict) else {}
    dimensions = raw.get("dimensions") if isinstance(raw.get("dimensions"), dict) else {}

    normalized_dimensions: dict[str, float] = {}
    for canonical, aliases in DIMENSION_ALIASES.items():
        normalized_dimensions[canonical] = _first_float(raw, dimensions, scores, aliases)

    total_score = _first_float(raw, dimensions, scores, ("total_score", "total", "overall", "score", "quality_score"))
    failures = _normalize_failures(raw.get("failures", []))
    counts = _failure_counts(raw, failures)

    return {
        "candidate_id": raw.get("candidate_id") or candidate_id or "unknown_candidate",
        "benchmark": raw.get("benchmark") or raw.get("benchmark_suite") or benchmark or "unknown_benchmark",
        "case_id": raw.get("case_id") or raw.get("id") or raw.get("test_id") or "unknown_case",
        "scoring_version": raw.get("scoring_version") or raw.get("scoring", {}).get("scorer_version") or scoring_version or "unknown_scoring",
        "total_score": round(float(total_score), 6),
        "dimensions": normalized_dimensions,
        "counts": counts,
        "failures": failures,
        "latency_ms": int(raw.get("latency_ms") or raw.get("latency") or raw.get("duration_ms") or 0),
        "cost_usd": float(raw.get("cost_usd") or raw.get("cost") or 0.0),
        "passed": bool(raw.get("passed", total_score >= 0.75 and not _has_critical_failures(failures))),
        "trace_refs": list(raw.get("trace_refs", [])),
        "source_refs": list(raw.get("source_refs", [])),
        "notes": raw.get("notes", []),
        "created_at": raw.get("created_at") or utc_now(),
    }


def reports_by_case(reports: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for report in reports:
        normalized = normalize_score_report(report)
        out[normalized["case_id"]] = normalized
    return out


def _first_float(raw: dict[str, Any], dimensions: dict[str, Any], scores: dict[str, Any], keys: tuple[str, ...]) -> float:
    for key in keys:
        for source in (raw, dimensions, scores):
            value = source.get(key)
            if value is None:
                continue
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    return 0.0


def _normalize_failures(raw_failures: Any) -> list[dict[str, Any]]:
    if raw_failures is None:
        return []
    if not isinstance(raw_failures, list):
        raw_failures = [raw_failures]
    failures: list[dict[str, Any]] = []
    for item in raw_failures:
        if isinstance(item, str):
            failures.append({"failure_type": item, "severity": "medium", "message": item})
        elif isinstance(item, dict):
            failure_type = str(item.get("failure_type") or item.get("type") or item.get("kind") or item.get("code") or "unknown_failure")
            failures.append({
                "failure_type": failure_type,
                "severity": str(item.get("severity") or "medium"),
                "message": str(item.get("message") or item.get("description") or failure_type),
                "trace_refs": list(item.get("trace_refs", [])),
                "source_refs": list(item.get("source_refs", [])),
            })
    return failures


def _failure_counts(raw: dict[str, Any], failures: list[dict[str, Any]]) -> dict[str, int]:
    counts = {key: int(raw.get(key) or 0) for key in FAILURE_COUNT_KEYS}
    raw_counts = raw.get("counts")
    if isinstance(raw_counts, dict):
        for key in FAILURE_COUNT_KEYS:
            if key in raw_counts:
                counts[key] = int(raw_counts.get(key) or 0)
    for failure in failures:
        key = FAILURE_TYPE_TO_COUNT.get(failure.get("failure_type", ""))
        if key:
            counts[key] += 1
    return counts


def _has_critical_failures(failures: list[dict[str, Any]]) -> bool:
    return any(str(f.get("severity", "")).lower() == "critical" for f in failures)
