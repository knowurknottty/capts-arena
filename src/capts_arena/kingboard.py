from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any


def build_kingboard(pairwise_reports: list[dict], benchmark_suite: str = "unknown") -> dict:
    """
    Build a kingboard ranking from a list of pairwise comparison reports.

    Parameters
    ----------
    pairwise_reports : list[dict]
        List of pairwise comparison reports.
    benchmark_suite : str
        Name of the benchmark suite these comparisons belong to.

    Returns
    -------
    dict
        Kingboard with ranked candidates.
    """
    candidates: dict[str, dict[str, Any]] = {}

    for report in pairwise_reports:
        for role in ("baseline_candidate", "challenger_candidate"):
            cid = report.get(role)
            if not cid:
                continue
            if cid not in candidates:
                candidates[cid] = {
                    "wins": 0,
                    "losses": 0,
                    "ties": 0,
                    "invalid_runs": 0,
                    "critical_regressions": 0,
                    "total_score": 0.0,
                    "count": 0,
                }

        winner = report.get("winner", "invalid")
        baseline = report.get("baseline_candidate", "")
        challenger = report.get("challenger_candidate", "")
        flags = report.get("regression_flags", [])

        if winner == "challenger":
            if challenger in candidates:
                candidates[challenger]["wins"] += 1
            if baseline in candidates:
                candidates[baseline]["losses"] += 1
        elif winner == "baseline":
            if baseline in candidates:
                candidates[baseline]["wins"] += 1
            if challenger in candidates:
                candidates[challenger]["losses"] += 1
        elif winner == "tie":
            if baseline in candidates:
                candidates[baseline]["ties"] += 1
            if challenger in candidates:
                candidates[challenger]["ties"] += 1
        elif winner == "invalid":
            if baseline in candidates:
                candidates[baseline]["invalid_runs"] += 1
            if challenger in candidates:
                candidates[challenger]["invalid_runs"] += 1

        # Track critical regressions
        has_critical = any(
            f in {
                "hallucinated_sources_increased",
                "unsupported_claims_increased",
                "stale_memory_regression",
                "contradiction_collapse_regression",
                "governance_violation_increased",
            }
            for f in flags
        )
        if has_critical and challenger in candidates:
            candidates[challenger]["critical_regressions"] += 1

        # Aggregate delta scores
        delta = report.get("delta", {})
        for cid in (baseline, challenger):
            if cid in candidates:
                candidates[cid]["total_score"] += abs(delta.get("total_score", 0))
                candidates[cid]["count"] += 0.5  # each report touches two candidates

    # Build ranking
    scored = []
    for cid, stats in candidates.items():
        arena_score = stats["total_score"] / max(stats["count"], 1)
        win_rate = stats["wins"] / max(stats["wins"] + stats["losses"] + stats["ties"], 1)

        # Determine promotion status
        if stats["critical_regressions"] > 0:
            status = "quarantined" if stats["critical_regressions"] >= 2 else "regressed"
        elif stats["wins"] > stats["losses"] and stats["invalid_runs"] == 0:
            status = "challenger"
        else:
            status = "challenger"

        scored.append(
            {
                "candidate_id": cid,
                "arena_score": round(arena_score, 4),
                "win_rate": round(win_rate, 4),
                "wins": stats["wins"],
                "losses": stats["losses"],
                "ties": stats["ties"],
                "invalid_runs": stats["invalid_runs"],
                "critical_regressions": stats["critical_regressions"],
                "promotion_status": status,
            }
        )

    # Sort by arena_score descending, then wins descending, then critical_regressions ascending
    scored.sort(key=lambda x: (x["arena_score"], x["wins"], -x["critical_regressions"]), reverse=True)

    for i, entry in enumerate(scored):
        entry["rank"] = i + 1
        if i == 0 and entry["promotion_status"] != "quarantined":
            entry["promotion_status"] = "king"

    current_king = scored[0]["candidate_id"] if scored else "none"

    return {
        "kingboard_version": "0.1.0",
        "kingboard_id": f"kb_{benchmark_suite}_{len(pairwise_reports)}_reports",
        "created_at": "",
        "benchmark_suite": benchmark_suite,
        "current_king": current_king,
        "rankings": scored,
    }