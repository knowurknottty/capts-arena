from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any


SEVERITY_MAP = {
    "hallucinated_source": "critical",
    "contradiction_collapsed": "critical",
    "adversarial_injection_accepted": "critical",
    "stale_memory_used": "high",
    "unsupported_claim": "high",
    "governance_violation": "high",
    "bad_retrieval": "medium",
    "bad_source_span": "medium",
    "compression_loss": "medium",
    "confidence_miscalibration": "low",
    "tool_use_failure": "medium",
    "answer_format_failure": "low",
}

FAILURE_TYPE_FROM_FLAG: dict[str, str] = {
    "hallucinated_sources_increased": "hallucinated_source",
    "unsupported_claims_increased": "unsupported_claim",
    "stale_memory_regression": "stale_memory_used",
    "contradiction_collapse_regression": "contradiction_collapsed",
    "governance_violation_increased": "governance_violation",
}


def export_failure_museum(pairwise_reports: list[dict]) -> list[dict]:
    """
    Extract failure artifacts from pairwise reports.

    Parameters
    ----------
    pairwise_reports : list[dict]
        List of pairwise comparison reports.

    Returns
    -------
    list[dict]
        Failure museum entries, one per meaningful failure/regression.
    """
    entries: list[dict] = []
    now = datetime.now(timezone.utc).isoformat()

    for report in pairwise_reports:
        if report.get("winner") == "invalid":
            continue

        flags = report.get("regression_flags", [])

        for flag in flags:
            failure_type = FAILURE_TYPE_FROM_FLAG.get(flag, "unsupported_claim")
            severity = SEVERITY_MAP.get(failure_type, "medium")

            museum_id = _make_museum_id(report, flag)

            entry: dict[str, Any] = {
                "museum_id": museum_id,
                "case_id": report.get("case_id", "unknown"),
                "candidate_id": report.get("challenger_candidate", report.get("baseline_candidate", "unknown")),
                "failure_type": failure_type,
                "severity": severity,
                "expected_behavior": report.get("notes", ""),
                "observed_behavior": f"Regression detected: {flag}",
                "trace_refs": [],
                "source_refs": [],
                "repair_recommendation": {
                    "repair_type": _repair_type(failure_type),
                    "description": f"Address regression: {flag}",
                    "candidate_bubble": severity in ("critical", "high"),
                },
                "regression": {
                    "is_regression": True,
                    "baseline_candidate": report.get("baseline_candidate", "unknown"),
                    "baseline_behavior": "Baseline did not have this regression.",
                },
                "museum_status": "open",
                "created_at": now,
            }

            entries.append(entry)

    return entries


def _make_museum_id(report: dict, flag: str) -> str:
    raw = f"{report.get('case_id', 'unknown')}_{flag}_{report.get('challenger_candidate', 'unknown')}"
    h = hashlib.sha256(raw.encode()).hexdigest()[:12]
    return f"failure_museum.{report.get('case_id', 'unknown')}.{h}"


def _repair_type(failure_type: str) -> str:
    mapping = {
        "hallucinated_source": "prompt",
        "contradiction_collapsed": "memory_policy",
        "stale_memory_used": "memory_policy",
        "unsupported_claim": "governance",
        "governance_violation": "governance",
        "bad_retrieval": "router",
        "compression_loss": "bubble",
    }
    return mapping.get(failure_type, "training")