from __future__ import annotations

from collections import defaultdict
from typing import Any

CRITICAL_FLAGS = {
    "hallucinated_sources_increased",
    "unsupported_claims_increased",
    "stale_memory_regression",
    "contradiction_collapse_regression",
    "governance_violation_increased",
}


def build_kingboard(pairwise_reports: list[dict[str, Any]], benchmark_suite: str = "unknown") -> dict[str, Any]:
    """Build deterministic candidate rankings from pairwise reports."""
    candidates: dict[str, dict[str, Any]] = defaultdict(_new_stats)

    for report in pairwise_reports:
        baseline = report.get("baseline_candidate")
        challenger = report.get("challenger_candidate")
        if baseline:
            candidates[baseline]["candidate_id"] = baseline
        if challenger:
            candidates[challenger]["candidate_id"] = challenger

        winner = report.get("winner", "invalid")
        flags = set(report.get("regression_flags", []))
        critical_count = sum(1 for flag in flags if flag in CRITICAL_FLAGS)

        if winner == "challenger" and challenger and baseline:
            candidates[challenger]["wins"] += 1
            candidates[baseline]["losses"] += 1
            candidates[challenger]["points"] += 3
            candidates[baseline]["points"] -= 1
        elif winner == "baseline" and challenger and baseline:
            candidates[baseline]["wins"] += 1
            candidates[challenger]["losses"] += 1
            candidates[baseline]["points"] += 3
            candidates[challenger]["points"] -= 1
        elif winner == "tie" and challenger and baseline:
            candidates[baseline]["ties"] += 1
            candidates[challenger]["ties"] += 1
            candidates[baseline]["points"] += 1
            candidates[challenger]["points"] += 1
        else:
            if baseline:
                candidates[baseline]["invalid_runs"] += 1
            if challenger:
                candidates[challenger]["invalid_runs"] += 1

        if challenger and critical_count:
            candidates[challenger]["critical_regressions"] += critical_count
            candidates[challenger]["points"] -= 5 * critical_count

        total_delta = float(report.get("delta", {}).get("total_score", 0.0) or 0.0)
        if challenger:
            candidates[challenger]["net_delta"] += total_delta
            candidates[challenger]["comparisons"] += 1
        if baseline:
            candidates[baseline]["net_delta"] -= total_delta
            candidates[baseline]["comparisons"] += 1

    rankings: list[dict[str, Any]] = []
    for candidate_id, stats in candidates.items():
        comparisons = max(int(stats["comparisons"]), 1)
        win_rate = stats["wins"] / max(stats["wins"] + stats["losses"] + stats["ties"], 1)
        avg_delta = stats["net_delta"] / comparisons
        arena_score = stats["points"] + (avg_delta * 10.0)

        if stats["critical_regressions"] >= 2:
            status = "quarantined"
        elif stats["critical_regressions"] == 1:
            status = "regressed"
        elif stats["invalid_runs"] > 0:
            status = "needs_more_evidence"
        else:
            status = "challenger"

        rankings.append({
            "candidate_id": candidate_id,
            "rank": 0,
            "arena_score": round(arena_score, 4),
            "win_rate": round(win_rate, 4),
            "wins": int(stats["wins"]),
            "losses": int(stats["losses"]),
            "ties": int(stats["ties"]),
            "invalid_runs": int(stats["invalid_runs"]),
            "critical_regressions": int(stats["critical_regressions"]),
            "net_delta": round(stats["net_delta"], 4),
            "avg_delta": round(avg_delta, 4),
            "promotion_status": status,
        })

    rankings.sort(key=lambda row: (
        row["promotion_status"] in {"quarantined", "regressed"},
        -row["arena_score"],
        -row["wins"],
        row["critical_regressions"],
        row["candidate_id"],
    ))

    current_king = "none"
    for index, entry in enumerate(rankings, start=1):
        entry["rank"] = index
        if current_king == "none" and entry["promotion_status"] not in {"quarantined", "regressed"}:
            entry["promotion_status"] = "king"
            current_king = entry["candidate_id"]

    return {
        "kingboard_version": "0.2.0",
        "kingboard_id": f"kb_{benchmark_suite}_{len(pairwise_reports)}_reports",
        "created_at": "",
        "benchmark_suite": benchmark_suite,
        "current_king": current_king,
        "rankings": rankings,
    }


def _new_stats() -> dict[str, Any]:
    return {
        "candidate_id": "",
        "points": 0.0,
        "wins": 0,
        "losses": 0,
        "ties": 0,
        "invalid_runs": 0,
        "critical_regressions": 0,
        "net_delta": 0.0,
        "comparisons": 0,
    }
