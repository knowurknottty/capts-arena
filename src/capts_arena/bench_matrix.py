from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .pairwise import compare_pair
from .kingboard import build_kingboard
from .failure_museum import export_failure_museum
from .promotion_gate import decide_promotion
from .score_report import load_score_reports, reports_by_case, write_json


def run_matrix(matrix_path: str | Path) -> dict[str, Any]:
    """Execute an Arena run matrix from real score-report files.

    No synthetic fallback is allowed. Every candidate must have a report path in
    candidate_reports or a reports_dir/{candidate_id}.json file.
    """
    matrix = json.loads(Path(matrix_path).read_text(encoding="utf-8"))
    _validate_matrix(matrix)

    arena_run_id = matrix["arena_run_id"]
    benchmark_suite = matrix["benchmark_suite"]
    scoring_version = matrix["scoring_version"]
    baseline_id = matrix["baseline_candidate"]
    challenger_ids = matrix["challenger_candidates"]
    all_candidates = [baseline_id] + challenger_ids

    outputs = matrix.get("outputs", {})
    run_root = Path(outputs.get("run_root", f".capts-arena/runs/{arena_run_id}"))
    pairwise_dir = Path(outputs.get("pairwise_reports_dir", run_root / "pairwise"))
    kingboard_path = Path(outputs.get("kingboard_path", run_root / "kingboard.json"))
    museum_dir = Path(outputs.get("failure_museum_dir", run_root / "failure_museum"))
    promotion_path = Path(outputs.get("promotion_path", run_root / "promotion_decisions.json"))

    for directory in (pairwise_dir, kingboard_path.parent, museum_dir, promotion_path.parent):
        directory.mkdir(parents=True, exist_ok=True)

    candidate_reports = {candidate_id: _load_candidate_reports(matrix, candidate_id) for candidate_id in all_candidates}
    baseline_by_case = reports_by_case(candidate_reports[baseline_id])
    pairwise_reports: list[dict[str, Any]] = []

    for challenger_id in challenger_ids:
        challenger_by_case = reports_by_case(candidate_reports[challenger_id])
        shared_case_ids = sorted(set(baseline_by_case).intersection(challenger_by_case))
        mismatched_case_ids = sorted(set(baseline_by_case).symmetric_difference(challenger_by_case))

        if mismatched_case_ids and matrix.get("strict_case_match", True):
            raise ValueError(f"Candidate {challenger_id} case set does not match baseline: {mismatched_case_ids}")
        if not shared_case_ids:
            raise ValueError(f"No shared case_id values between baseline and {challenger_id}")

        for case_id in shared_case_ids:
            report = compare_pair(baseline_by_case[case_id], challenger_by_case[case_id])
            pairwise_reports.append(report)
            write_json(pairwise_dir / f"{report['comparison_id']}.json", report)

    kingboard = build_kingboard(pairwise_reports, benchmark_suite)
    write_json(kingboard_path, kingboard)

    museum_entries = export_failure_museum(pairwise_reports)
    for entry in museum_entries:
        write_json(museum_dir / f"{entry['museum_id']}.json", entry)

    promotions = [decide_promotion(challenger_id, kingboard, pairwise_reports) for challenger_id in challenger_ids]
    write_json(promotion_path, promotions)

    return {
        "arena_run_id": arena_run_id,
        "benchmark_suite": benchmark_suite,
        "scoring_version": scoring_version,
        "baseline_candidate": baseline_id,
        "challenger_candidates": challenger_ids,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "candidate_results": {
            candidate_id: {
                "cases_run": len(candidate_reports[candidate_id]),
                "cases_passed": sum(1 for report in candidate_reports[candidate_id] if report.get("passed", False)),
                "avg_score": _avg_score(candidate_reports[candidate_id]),
            }
            for candidate_id in all_candidates
        },
        "pairwise_count": len(pairwise_reports),
        "kingboard": {
            "current_king": kingboard["current_king"],
            "rankings": len(kingboard["rankings"]),
            "rankings_list": [row["candidate_id"] for row in kingboard["rankings"]],
        },
        "failure_museum_entries": len(museum_entries),
        "promotions": promotions,
        "outputs": {
            "run_root": str(run_root),
            "pairwise_reports_dir": str(pairwise_dir),
            "kingboard_path": str(kingboard_path),
            "failure_museum_dir": str(museum_dir),
            "promotion_path": str(promotion_path),
        },
    }


def _validate_matrix(matrix: dict[str, Any]) -> None:
    required = ["arena_run_id", "benchmark_suite", "scoring_version", "baseline_candidate", "challenger_candidates"]
    for field in required:
        if field not in matrix:
            raise ValueError(f"Run matrix missing required field: {field}")
    if not isinstance(matrix["challenger_candidates"], list) or not matrix["challenger_candidates"]:
        raise ValueError("challenger_candidates must be a non-empty list")


def _load_candidate_reports(matrix: dict[str, Any], candidate_id: str) -> list[dict[str, Any]]:
    candidate_report_paths = matrix.get("candidate_reports", {})
    if candidate_id in candidate_report_paths:
        return load_score_reports(candidate_report_paths[candidate_id])

    reports_dir = matrix.get("reports_dir")
    if reports_dir:
        report_path = Path(reports_dir) / f"{candidate_id}.json"
        if report_path.exists():
            return load_score_reports(report_path)

    raise FileNotFoundError(
        f"No score reports for candidate {candidate_id!r}. Provide candidate_reports or reports_dir/{candidate_id}.json."
    )


def _avg_score(reports: list[dict[str, Any]]) -> float:
    scores = [float(report.get("total_score", report.get("scores", {}).get("total", 0.0)) or 0.0) for report in reports]
    return round(sum(scores) / max(len(scores), 1), 4)
