from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


CRITICAL_REGRESSION_FLAGS = {
    "hallucinated_sources_increased",
    "unsupported_claims_increased",
    "stale_memory_regression",
    "contradiction_collapse_regression",
    "governance_violation_increased",
}


def decide_promotion(candidate_id: str, kingboard: dict, pairwise_reports: list[dict]) -> dict:
    """
    Decide whether a candidate should be promoted based on kingboard and pairwise reports.

    Parameters
    ----------
    candidate_id : str
        The candidate to evaluate for promotion.
    kingboard : dict
        Current kingboard state.
    pairwise_reports : list[dict]
        Pairwise comparison reports involving this candidate.

    Returns
    -------
    dict
        Promotion decision.
    """
    now = datetime.now(timezone.utc).isoformat()
    current_king = kingboard.get("current_king", "")
    rankings = kingboard.get("rankings", [])

    # Find candidate in rankings
    candidate_rank = None
    for r in rankings:
        if r["candidate_id"] == candidate_id:
            candidate_rank = r
            break

    if candidate_rank is None:
        return _decision(candidate_id, current_king, "needs_more_evidence", "Candidate not found in kingboard.", now)

    # Check 1: critical regressions
    if candidate_rank.get("critical_regressions", 0) > 0:
        return _decision(
            candidate_id,
            current_king,
            "reject",
            f"Candidate has {candidate_rank['critical_regressions']} critical regression(s). Integrity failures dominate capability gains.",
            now,
        )

    # Check 2: must beat current king
    if candidate_rank["rank"] > 1 and current_king != candidate_id:
        # Need to check head-to-head
        head_to_head = _head_to_head(candidate_id, current_king, pairwise_reports)

        if not head_to_head:
            return _decision(candidate_id, current_king, "needs_more_evidence", "No head-to-head comparison with current king.", now)

        if head_to_head["challenger_wins"] <= head_to_head["baseline_wins"]:
            return _decision(
                candidate_id,
                current_king,
                "reject",
                f"Challenger wins {head_to_head['challenger_wins']} vs baseline wins {head_to_head['baseline_wins']}. Must beat current king.",
                now,
            )

    # Check 3: invalid runs
    if candidate_rank.get("invalid_runs", 0) > 0:
        return _decision(
            candidate_id,
            current_king,
            "needs_more_evidence",
            f"{candidate_rank['invalid_runs']} invalid run(s). Some comparisons may be contaminated.",
            now,
        )

    # All checks passed
    if candidate_id == current_king:
        return _decision(candidate_id, current_king, "promote", "King retained position.", now)
    else:
        return _decision(candidate_id, current_king, "promote", f"Challenger beat current king ({current_king}) with no critical regressions.", now)


def _head_to_head(challenger: str, baseline: str, reports: list[dict]) -> dict | None:
    """Count head-to-head wins between two candidates."""
    baseline_wins = 0
    challenger_wins = 0

    for r in reports:
        b = r.get("baseline_candidate", "")
        c = r.get("challenger_candidate", "")
        if not ({b, c} == {challenger, baseline}):
            continue

        winner = r.get("winner", "")
        if winner == "baseline":
            baseline_wins += 1
        elif winner == "challenger":
            challenger_wins += 1

    if baseline_wins == 0 and challenger_wins == 0:
        return None

    return {"baseline_wins": baseline_wins, "challenger_wins": challenger_wins}


def _decision(candidate_id: str, baseline: str, decision: str, reason: str, now: str) -> dict:
    return {
        "promotion_id": f"promo_{candidate_id}_{now[:10]}",
        "candidate_id": candidate_id,
        "baseline_candidate": baseline,
        "decision": decision,
        "reason": reason,
        "required_followups": [],
        "supporting_reports": [],
        "blocked_by": [],
        "created_at": now,
    }