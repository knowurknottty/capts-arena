from __future__ import annotations

from typing import Any

from .score_report import CANONICAL_DIMENSIONS, normalize_score_report, utc_now

CRITICAL_REGRESSIONS = {
    "hallucinated_sources_increased",
    "unsupported_claims_increased",
    "stale_memory_regression",
    "contradiction_collapse_regression",
    "governance_violation_increased",
}

DIMENSION_REGRESSION_LIMIT = -0.05
WIN_THRESHOLD = 0.05


def compare_pair(baseline: dict[str, Any], challenger: dict[str, Any]) -> dict[str, Any]:
    """Compare two candidate case reports.

    Integrity dominates fluency: a challenger with a higher raw score still loses
    if it introduces critical regressions such as hallucinated sources,
    unsupported claims, stale memory reuse, contradiction collapse, or governance
    violations.
    """
    baseline_n = normalize_score_report(baseline)
    challenger_n = normalize_score_report(challenger)

    manifest_compatible, reason = _check_manifest_compatibility(baseline_n, challenger_n)
    if not manifest_compatible:
        return _invalid_report(baseline_n, challenger_n, reason)

    delta: dict[str, Any] = {
        "total_score": _round(challenger_n["total_score"] - baseline_n["total_score"]),
        "latency_ms": int(challenger_n["latency_ms"] - baseline_n["latency_ms"]),
        "cost_usd": _round(challenger_n["cost_usd"] - baseline_n["cost_usd"], 6),
    }

    for dimension in CANONICAL_DIMENSIONS:
        delta[dimension] = _round(challenger_n["dimensions"].get(dimension, 0.0) - baseline_n["dimensions"].get(dimension, 0.0))

    for count_key in ("unsupported_claims", "hallucinated_sources"):
        delta[count_key] = int(challenger_n["counts"].get(count_key, 0) - baseline_n["counts"].get(count_key, 0))

    regression_flags = _regression_flags(baseline_n, challenger_n, delta)
    has_critical = any(flag in CRITICAL_REGRESSIONS for flag in regression_flags)

    if has_critical:
        winner = "baseline"
    elif delta["total_score"] > WIN_THRESHOLD:
        winner = "challenger"
    elif delta["total_score"] < -WIN_THRESHOLD:
        winner = "baseline"
    else:
        winner = "tie"

    return {
        "comparison_id": _comparison_id(baseline_n, challenger_n),
        "baseline_candidate": baseline_n["candidate_id"],
        "challenger_candidate": challenger_n["candidate_id"],
        "benchmark": baseline_n["benchmark"],
        "case_id": baseline_n["case_id"],
        "winner": winner,
        "delta": delta,
        "regression_flags": regression_flags,
        "promotion_relevant": True,
        "notes": _generate_notes(winner, delta, regression_flags),
        "evidence_summary": {
            "baseline_failures": baseline_n["failures"],
            "challenger_failures": challenger_n["failures"],
            "baseline_trace_refs": baseline_n["trace_refs"],
            "challenger_trace_refs": challenger_n["trace_refs"],
            "baseline_source_refs": baseline_n["source_refs"],
            "challenger_source_refs": challenger_n["source_refs"],
        },
        "created_at": challenger_n.get("created_at") or utc_now(),
    }


def _check_manifest_compatibility(baseline: dict[str, Any], challenger: dict[str, Any]) -> tuple[bool, str]:
    checks = (
        ("scoring_version", "different scoring version"),
        ("benchmark", "different benchmark"),
        ("case_id", "different case id"),
    )
    for key, reason in checks:
        b = baseline.get(key)
        c = challenger.get(key)
        if b and c and b != c:
            return False, reason
    return True, ""


def _regression_flags(baseline: dict[str, Any], challenger: dict[str, Any], delta: dict[str, Any]) -> list[str]:
    flags: list[str] = []

    if delta.get("hallucinated_sources", 0) > 0:
        flags.append("hallucinated_sources_increased")
    if delta.get("unsupported_claims", 0) > 0:
        flags.append("unsupported_claims_increased")

    count_deltas = {
        "stale_memory_uses": "stale_memory_regression",
        "contradiction_collapses": "contradiction_collapse_regression",
        "governance_violations": "governance_violation_increased",
    }
    for count_key, flag in count_deltas.items():
        before = int(baseline["counts"].get(count_key, 0))
        after = int(challenger["counts"].get(count_key, 0))
        if after > before:
            flags.append(flag)

    if delta.get("stale_rejection", 0.0) < DIMENSION_REGRESSION_LIMIT and "stale_memory_regression" not in flags:
        flags.append("stale_memory_regression")
    if delta.get("contradiction_preservation", 0.0) < DIMENSION_REGRESSION_LIMIT and "contradiction_collapse_regression" not in flags:
        flags.append("contradiction_collapse_regression")
    if delta.get("source_grounding", 0.0) < DIMENSION_REGRESSION_LIMIT:
        flags.append("source_grounding_regression")
    if delta.get("citation_accuracy", 0.0) < DIMENSION_REGRESSION_LIMIT:
        flags.append("citation_accuracy_regression")

    return flags


def _invalid_report(baseline: dict[str, Any], challenger: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "comparison_id": f"cmp_invalid_{baseline.get('candidate_id', '?')}_vs_{challenger.get('candidate_id', '?')}",
        "baseline_candidate": baseline.get("candidate_id", "?"),
        "challenger_candidate": challenger.get("candidate_id", "?"),
        "benchmark": baseline.get("benchmark", "?"),
        "case_id": baseline.get("case_id", "?"),
        "winner": "invalid",
        "delta": {
            "total_score": 0.0,
            "unsupported_claims": 0,
            "hallucinated_sources": 0,
            "latency_ms": 0,
            "cost_usd": 0.0,
        },
        "regression_flags": [f"incompatible_run_manifests: {reason}"],
        "promotion_relevant": False,
        "notes": f"Run manifests incompatible: {reason}.",
        "created_at": utc_now(),
    }


def _comparison_id(baseline: dict[str, Any], challenger: dict[str, Any]) -> str:
    return (
        f"cmp_{baseline.get('candidate_id', 'baseline')}"
        f"_vs_{challenger.get('candidate_id', 'challenger')}"
        f"_{baseline.get('case_id', 'unknown')}"
    )


def _generate_notes(winner: str, delta: dict[str, Any], flags: list[str]) -> str:
    parts: list[str] = []
    if flags:
        parts.append(f"Regressions: {', '.join(flags)}.")
    if winner == "baseline" and any(flag in CRITICAL_REGRESSIONS for flag in flags):
        parts.append("Integrity failure dominates capability gain.")
    elif winner == "challenger":
        parts.append("Challenger produced a meaningful positive delta with no critical regressions.")
    elif winner == "tie":
        parts.append("Delta is within tolerance; keep more evidence before promotion.")
    if delta.get("total_score", 0.0) > 0.15:
        parts.append("Strong positive raw delta.")
    return " ".join(parts)


def _round(value: float, places: int = 4) -> float:
    return round(float(value), places)
