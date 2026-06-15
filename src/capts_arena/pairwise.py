from __future__ import annotations

import json
from pathlib import Path
from typing import Any


CRITICAL_REGRESSIONS = {
    "hallucinated_sources_increased",
    "unsupported_claims_increased",
    "stale_memory_regression",
    "contradiction_collapse_regression",
    "governance_violation_increased",
}


def compare_pair(baseline: dict, challenger: dict) -> dict:
    """
    Compare two candidate score reports and produce a pairwise delta report.

    Parameters
    ----------
    baseline : dict
        Score report for the baseline candidate.
    challenger : dict
        Score report for the challenger candidate.

    Returns
    -------
    dict
        Pairwise comparison report with delta, winner, and regression flags.
    """
    # Validate manifest compatibility
    regression_flags: list[str] = []
    manifest_compatible = _check_manifest_compatibility(baseline, challenger)

    if not manifest_compatible:
        return _invalid_report(baseline, challenger, "incompatible_run_manifests")

    # Compute raw delta on every dimension
    delta: dict[str, Any] = {
        "total_score": _float_diff(baseline, challenger, "total_score"),
        "answer_correctness": _float_diff(baseline, challenger, "answer_correctness"),
        "stale_rejection": _float_diff(baseline, challenger, "stale_rejection"),
        "contradiction_preservation": _float_diff(baseline, challenger, "contradiction_preservation"),
        "citation_accuracy": _float_diff(baseline, challenger, "citation_accuracy"),
        "source_grounding": _float_diff(baseline, challenger, "source_grounding"),
        "unsupported_claims": _int_diff(baseline, challenger, "unsupported_claims"),
        "hallucinated_sources": _int_diff(baseline, challenger, "hallucinated_sources"),
        "latency_ms": _int_diff(baseline, challenger, "latency_ms"),
        "cost_usd": _float_diff(baseline, challenger, "cost_usd"),
    }

    # Detect regressions
    if delta.get("hallucinated_sources", 0) > 0:
        regression_flags.append("hallucinated_sources_increased")
    if delta.get("unsupported_claims", 0) > 0:
        regression_flags.append("unsupported_claims_increased")

    # Determine winner
    has_critical = any(f in CRITICAL_REGRESSIONS for f in regression_flags)
    delta_total = delta.get("total_score", 0.0)

    if has_critical:
        if delta_total > 0:
            # Has a critical regression but higher score — baseline wins (integrity > capability)
            winner = "baseline"
        elif delta_total < 0:
            winner = "baseline"
        else:
            winner = "baseline"
    elif delta_total > 0.05:
        winner = "challenger"
    elif delta_total < -0.05:
        winner = "baseline"
    else:
        winner = "tie"

    # Decide if this comparison is relevant for promotion
    promotion_relevant = winner != "invalid" and not manifest_compatible is False  # noqa: E712

    return {
        "comparison_id": f"cmp_{baseline.get('candidate_id', 'baseline')}_vs_{challenger.get('candidate_id', 'challenger')}_{challenger.get('case_id', 'unknown')}",
        "baseline_candidate": baseline.get("candidate_id", "baseline"),
        "challenger_candidate": challenger.get("candidate_id", "challenger"),
        "benchmark": baseline.get("benchmark", "unknown"),
        "case_id": baseline.get("case_id", "unknown"),
        "winner": winner,
        "delta": delta,
        "regression_flags": regression_flags,
        "promotion_relevant": promotion_relevant,
        "notes": _generate_notes(winner, delta, regression_flags),
        "created_at": baseline.get("created_at", ""),
    }


def _check_manifest_compatibility(baseline: dict, challenger: dict) -> bool:
    """Check that two score reports come from compatible runs."""
    b_scoring = baseline.get("scoring_version") or baseline.get("scoring", {}).get("scorer_version")
    c_scoring = challenger.get("scoring_version") or challenger.get("scoring", {}).get("scorer_version")
    if b_scoring and c_scoring and b_scoring != c_scoring:
        return False

    b_bench = baseline.get("benchmark")
    c_bench = challenger.get("benchmark")
    if b_bench and c_bench and b_bench != c_bench:
        return False

    b_case = baseline.get("case_id")
    c_case = challenger.get("case_id")
    if b_case and c_case and b_case != c_case:
        return False

    return True


def _invalid_report(baseline: dict, challenger: dict, reason: str) -> dict:
    return {
        "comparison_id": f"cmp_invalid_{baseline.get('candidate_id', '?')}_vs_{challenger.get('candidate_id', '?')}",
        "baseline_candidate": baseline.get("candidate_id", "?"),
        "challenger_candidate": challenger.get("candidate_id", "?"),
        "benchmark": baseline.get("benchmark", "?"),
        "case_id": baseline.get("case_id", "?"),
        "winner": "invalid",
        "delta": {"total_score": 0.0},
        "regression_flags": [f"incompatible_run_manifests: {reason}"],
        "promotion_relevant": False,
        "notes": f"Run manifests incompatible: {reason}",
        "created_at": baseline.get("created_at", ""),
    }


def _float_diff(b: dict, c: dict, key: str) -> float:
    return float(c.get(key, 0) or 0) - float(b.get(key, 0) or 0)


def _int_diff(b: dict, c: dict, key: str) -> int:
    return int(c.get(key, 0) or 0) - int(b.get(key, 0) or 0)


def _generate_notes(winner: str, delta: dict, flags: list[str]) -> str:
    if winner == "invalid":
        return "Run manifests incompatible. Comparison invalid."
    parts = []
    if flags:
        parts.append(f"Regressions: {', '.join(flags)}")
    if winner == "baseline" and any("increased" in f for f in flags):
        parts.append("Integrity failure dominates capability gain.")
    if delta.get("total_score", 0) > 0.15:
        parts.append("Strong positive delta.")
    return " ".join(parts) if parts else ""