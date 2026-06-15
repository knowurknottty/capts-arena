from __future__ import annotations

import json
from pathlib import Path

from capts_arena.bench_matrix import run_matrix


FIXTURES = Path(__file__).parent.parent / "benchmarks" / "arena"


class TestBenchMatrix:
    """Tests for the bench-matrix pipeline (capt-context bridge)."""

    def test_run_matrix_from_fixture(self):
        matrix_path = FIXTURES / "demo_run_matrix.json"
        report = run_matrix(str(matrix_path))
        assert report["arena_run_id"] == "demo_001"
        assert report["baseline_candidate"] == "biocapt_v2_1_baseline"
        assert len(report["challenger_candidates"]) == 2
        assert report["kingboard"]["current_king"] is not None
        assert report["pairwise_count"] >= 2
        assert isinstance(report["kingboard"]["rankings"], int)
        assert report["kingboard"]["rankings"] >= 1

    def test_run_matrix_output_shape(self):
        matrix_path = FIXTURES / "demo_run_matrix.json"
        report = run_matrix(str(matrix_path))
        required_keys = {
            "arena_run_id", "benchmark_suite", "baseline_candidate",
            "challenger_candidates", "created_at", "candidate_results",
            "pairwise_count", "kingboard", "failure_museum_entries",
            "promotions", "outputs",
        }
        assert required_keys.issubset(set(report.keys()))

    def test_run_matrix_candidate_results(self):
        matrix_path = FIXTURES / "demo_run_matrix.json"
        report = run_matrix(str(matrix_path))
        for cid in report["candidate_results"]:
            cr = report["candidate_results"][cid]
            assert "cases_run" in cr
            assert "cases_passed" in cr
            assert "avg_score" in cr
            assert cr["avg_score"] > 0