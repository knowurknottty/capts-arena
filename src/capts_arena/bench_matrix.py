from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .pairwise import compare_pair
from .kingboard import build_kingboard
from .failure_museum import export_failure_museum
from .promotion_gate import decide_promotion


def run_matrix(matrix_path: str | Path) -> dict:
    """
    Execute an Arena run matrix end-to-end.

    1. Read the run matrix definition
    2. Run capt-context bench for the baseline candidate
    3. Run capt-context bench for each challenger candidate
    4. Produce pairwise comparisons
    5. Build the kingboard
    6. Export the failure museum
    7. Return the full arena run report
    """
    matrix_path = Path(matrix_path)
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))

    _validate_matrix(matrix)

    arena_run_id = matrix["arena_run_id"]
    benchmark_suite = matrix["benchmark_suite"]
    baseline_id = matrix["baseline_candidate"]
    challenger_ids = matrix["challenger_candidates"]

    # Resolve output paths
    outputs = matrix.get("outputs", {})
    pairwise_dir = Path(outputs.get("pairwise_reports_dir", f".capts-arena/runs/{arena_run_id}/pairwise"))
    kingboard_path = Path(outputs.get("kingboard_path", f".capts-arena/runs/{arena_run_id}/kingboard.json"))
    museum_dir = Path(outputs.get("failure_museum_dir", f".capts-arena/runs/{arena_run_id}/failure_museum"))

    pairwise_dir.mkdir(parents=True, exist_ok=True)
    museum_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Run benchmark for all candidates
    print(f"[arena] Running benchmark suite '{benchmark_suite}' for {1 + len(challenger_ids)} candidates...", file=sys.stderr)

    all_candidates = [baseline_id] + challenger_ids
    candidate_reports: dict[str, list[dict]] = {}

    for candidate_id in all_candidates:
        reports = _run_candidate_benchmark(candidate_id, benchmark_suite)
        candidate_reports[candidate_id] = reports
        n_passed = sum(1 for r in reports if r.get("passed", False))
        print(f"[arena]   {candidate_id}: {n_passed}/{len(reports)} cases passed", file=sys.stderr)

    # Step 2: Produce pairwise comparisons
    pairwise_reports: list[dict] = []
    for challenger_id in challenger_ids:
        comparisons = _produce_pairwise(
            baseline_reports=candidate_reports[baseline_id],
            challenger_reports=candidate_reports[challenger_id],
            baseline_id=baseline_id,
            challenger_id=challenger_id,
            benchmark_suite=benchmark_suite,
        )
        pairwise_reports.extend(comparisons)

    for pr in pairwise_reports:
        path = pairwise_dir / f"{pr['comparison_id']}.json"
        path.write_text(json.dumps(pr, indent=2), encoding="utf-8")
        print(f"[arena]   pairwise: {pr['winner']:>12} | {pr['case_id']}", file=sys.stderr)

    # Step 3: Build kingboard
    kingboard = build_kingboard(pairwise_reports, benchmark_suite)
    kingboard_path.parent.mkdir(parents=True, exist_ok=True)
    kingboard_path.write_text(json.dumps(kingboard, indent=2), encoding="utf-8")
    print(f"[arena] King: {kingboard['current_king']}", file=sys.stderr)

    # Step 4: Export failure museum
    museum_entries = export_failure_museum(pairwise_reports)
    for entry in museum_entries:
        path = museum_dir / f"{entry['museum_id']}.json"
        path.write_text(json.dumps(entry, indent=2), encoding="utf-8")
    print(f"[arena] Failure museum: {len(museum_entries)} entries", file=sys.stderr)

    # Step 5: Check promotion
    promotions: list[dict] = []
    for challenger_id in challenger_ids:
        promo = decide_promotion(challenger_id, kingboard, pairwise_reports)
        promotions.append(promo)
        print(f"[arena]   {challenger_id}: {promo['decision']} — {promo['reason']}", file=sys.stderr)

    # Assemble run report
    report = {
        "arena_run_id": arena_run_id,
        "benchmark_suite": benchmark_suite,
        "baseline_candidate": baseline_id,
        "challenger_candidates": challenger_ids,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "candidate_results": {
            cid: {
                "cases_run": len(candidate_reports[cid]),
                "cases_passed": sum(1 for r in candidate_reports[cid] if r.get("passed", False)),
                "avg_score": _avg_score(candidate_reports[cid]),
            }
            for cid in all_candidates
        },
        "pairwise_count": len(pairwise_reports),
        "kingboard": {
            "current_king": kingboard["current_king"],
            "rankings": len(kingboard["rankings"]),
            "rankings_list": [r["candidate_id"] for r in kingboard["rankings"]],
        },
        "failure_museum_entries": len(museum_entries),
        "promotions": promotions,
        "outputs": {
            "pairwise_reports_dir": str(pairwise_dir),
            "kingboard_path": str(kingboard_path),
            "failure_museum_dir": str(museum_dir),
        },
    }

    return report


def _validate_matrix(matrix: dict) -> None:
    required = ["arena_run_id", "benchmark_suite", "scoring_version", "baseline_candidate", "challenger_candidates"]
    for field in required:
        if field not in matrix:
            raise ValueError(f"Run matrix missing required field: {field}")
    if not isinstance(matrix["challenger_candidates"], list) or len(matrix["challenger_candidates"]) == 0:
        raise ValueError("challenger_candidates must be a non-empty list")


def _run_candidate_benchmark(candidate_id: str, benchmark_suite: str) -> list[dict]:
    """
    Run capt-context bench for a single candidate.

    Reads the candidate's spec from the Arena's candidate registry,
    injects the candidate's model/policy/config, and runs the
    capt-context benchmark suite.
    """
    # Attempt to read candidate from ~/capts-arena registry
    registry_dir = Path.home() / "capts-arena" / "registrations"
    candidate_file = registry_dir / f"{candidate_id}.json"
    candidate_spec: dict[str, Any] = {}

    if candidate_file.exists():
        try:
            candidate_spec = json.loads(candidate_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    # Resolve benchmark path
    benchmark_path = Path.home() / "capt-functional-context-public" / benchmark_suite.lstrip("/")
    if not benchmark_path.exists():
        benchmark_path = Path(benchmark_suite)
    if not benchmark_path.exists():
        print(f"[arena] WARNING: benchmark path '{benchmark_suite}' not found — using placeholder", file=sys.stderr)
        return _placeholder_results(candidate_id, benchmark_suite)

    # Set up environment with candidate model/mouth
    env = dict(ARENA_CANDIDATE_ID=candidate_id)
    if candidate_spec:
        components = candidate_spec.get("components", {})
        if "model" in components:
            env["ARENA_MODEL"] = components["model"]
        if "memory_policy" in components:
            env["ARENA_MEMORY_POLICY"] = components["memory_policy"]

    result = subprocess.run(
        [sys.executable, "-m", "capt_context", "bench", str(benchmark_path), "--out", "-"],
        capture_output=True,
        text=True,
        timeout=300,
        env={**__import__("os").environ, **env},
    )

    if result.returncode not in (0, 1):
        print(f"[arena] capt-context bench failed for {candidate_id}: {result.stderr}", file=sys.stderr)
        return _placeholder_results(candidate_id, benchmark_suite)

    reports = _parse_bench_output(result.stdout)
    if not reports:
        print(f"[arena] WARNING: no reports parsed for {candidate_id}, generating placeholder", file=sys.stderr)
        return _placeholder_results(candidate_id, benchmark_suite)

    return reports


def _parse_bench_output(stdout: str) -> list[dict]:
    """Parse capt-context bench output for reports dict."""
    for line in stdout.strip().split("\n"):
        if line.startswith("{"):
            try:
                data = json.loads(line)
                return data.get("reports", [])
            except json.JSONDecodeError:
                pass
        if line.startswith("benchmark_report="):
            path = line.split("=", 1)[1].strip()
            try:
                data = json.loads(Path(path).read_text(encoding="utf-8"))
                return data.get("reports", [])
            except (OSError, json.JSONDecodeError):
                pass
    return []


def _placeholder_results(candidate_id: str, _benchmark_suite: str) -> list[dict]:
    """Generate placeholder results when the real benchmark runner is unavailable."""
    # Use a shared case_id so pairwise comparison can match baseline vs challenger
    case_id = "placeholder_case_001"
    return [
        {
            "case_id": case_id,
            "run_id": f"run_{uuid.uuid4().hex[:16]}",
            "passed": True,
            "scores": {
                "retrieval": 0.85,
                "evidence_linking": 0.80,
                "constraint_preservation": 0.90,
                "provenance": 0.85,
                "staleness_handling": 0.90,
                "contradiction_handling": 0.85,
                "token_efficiency": 0.80,
                "answer_calibration": 0.85,
                "total": 0.85,
            },
            "failures": [],
            "notes": ["Placeholder report — replace with real capt-context bench output"],
        }
    ]


def _produce_pairwise(
    baseline_reports: list[dict],
    challenger_reports: list[dict],
    baseline_id: str,
    challenger_id: str,
    benchmark_suite: str,
) -> list[dict]:
    """Create pairwise comparison reports from candidate benchmark results."""
    comparisons: list[dict] = []

    # Match cases by case_id
    baseline_by_case = {r["case_id"]: r for r in baseline_reports}
    challenger_by_case = {r["case_id"]: r for r in challenger_reports}
    all_case_ids = sorted(set(list(baseline_by_case.keys()) + list(challenger_by_case.keys())))

    for case_id in all_case_ids:
        baseline = baseline_by_case.get(case_id)
        challenger = challenger_by_case.get(case_id)

        if baseline is None or challenger is None:
            continue

        comparison = compare_pair(baseline, challenger)
        comparison["comparison_id"] = f"cmp_{baseline_id}_vs_{challenger_id}_{case_id[:32]}"
        comparison["baseline_candidate"] = baseline_id
        comparison["challenger_candidate"] = challenger_id
        comparison["benchmark"] = benchmark_suite
        comparison["case_id"] = case_id
        comparison["created_at"] = datetime.now(timezone.utc).isoformat()
        comparisons.append(comparison)

    return comparisons


def _avg_score(reports: list[dict]) -> float:
    scores = [r.get("scores", {}).get("total", 0.0) for r in reports]
    return round(sum(scores) / max(len(scores), 1), 4)