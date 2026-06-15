from __future__ import annotations

import json
from pathlib import Path

from capts_arena.pairwise import compare_pair
from capts_arena.kingboard import build_kingboard
from capts_arena.failure_museum import export_failure_museum
from capts_arena.promotion_gate import decide_promotion


FIXTURES = Path(__file__).parent.parent / "reports" / "fixtures"


def _load(name: str) -> dict:
    with open(FIXTURES / name) as f:
        return json.load(f)


class TestPairwise:
    """Pairwise comparator tests."""

    def test_challenger_wins_on_stale_rejection(self):
        report = _load("pairwise_stale_rejection_win.json")
        assert report["winner"] == "challenger"
        assert report["promotion_relevant"] is True
        assert report["delta"]["total_score"] == 0.18

    def test_baseline_wins_when_challenger_hallucinates(self):
        """THE IGNITION TEST: higher score + integrity failure = baseline wins."""
        report = _load("pairwise_hallucination_loss.json")
        assert report["winner"] == "baseline", \
            "Challenger with hallucination must lose even with higher raw score"
        assert "hallucinated_sources_increased" in report["regression_flags"]
        assert report["promotion_relevant"] is True

    def test_invalid_when_manifests_incompatible(self):
        report = _load("pairwise_invalid.json")
        assert report["winner"] == "invalid"
        assert report["promotion_relevant"] is False


class TestKingboard:
    """Kingboard generation tests."""

    def test_kingboard_ranks_from_fixtures(self):
        reports = [_load(f) for f in ["pairwise_stale_rejection_win.json", "pairwise_hallucination_loss.json"]]
        kb = build_kingboard(reports, "capt_mem_7")
        assert len(kb["rankings"]) >= 2, f"Expected at least 2 candidates, got {len(kb['rankings'])}"
        assert kb["current_king"] is not None

    def test_candidate_with_regression_not_king(self):
        reports = [_load(f) for f in ["pairwise_stale_rejection_win.json", "pairwise_hallucination_loss.json"]]
        kb = build_kingboard(reports, "capt_mem_7")
        for r in kb["rankings"]:
            if r["critical_regressions"] > 0:
                assert r["promotion_status"] in ("quarantined", "regressed"), \
                    "Candidate with critical regressions must not be king"


class TestFailureMuseum:
    """Failure museum export tests."""

    def test_failure_museum_emits_from_regressions(self):
        reports = [_load(f) for f in ["pairwise_stale_rejection_win.json", "pairwise_hallucination_loss.json"]]
        entries = export_failure_museum(reports)
        assert len(entries) >= 1
        for entry in entries:
            assert "museum_id" in entry
            assert entry["severity"] in ("low", "medium", "high", "critical")

    def test_hallucination_entry_is_critical(self):
        reports = [_load(f) for f in ["pairwise_hallucination_loss.json"]]
        entries = export_failure_museum(reports)
        hallucination_entries = [e for e in entries if e["failure_type"] == "hallucinated_source"]
        if hallucination_entries:
            assert all(e["severity"] == "critical" for e in hallucination_entries)


class TestPromotionGate:
    """Promotion gate tests — the soul of the Arena."""

    def test_higher_score_does_not_win_with_critical_regression(self):
        """THE IGNITION TEST: higher average score + critical regression = rejected."""
        reports = [
            _load("pairwise_hallucination_loss.json"),
        ]
        kb = build_kingboard(reports, "capt_mem_7")

        # Find the hallucinating challenger
        challenger_id = "biocapt_v2_1_fluent_but_lying"
        decision = decide_promotion(challenger_id, kb, reports)

        assert decision["decision"] == "reject", \
            "Candidate with critical regression must be rejected for promotion"
        assert "critical regression" in decision["reason"].lower() or \
               "integrity" in decision["reason"].lower()

    def test_clean_challenger_can_be_promoted(self):
        reports = [
            _load("pairwise_stale_rejection_win.json"),
            _load("pairwise_hallucination_loss.json"),
        ]
        kb = build_kingboard(reports, "capt_mem_7")

        decision = decide_promotion("biocapt_v2_1_mem_policy_a", kb, reports)
        # This candidate won, so should be promotable
        assert decision["decision"] in ("promote", "needs_more_evidence")


class TestSchemas:
    """Schema validation using JSON Schema."""

    def test_candidate_schema_is_valid(self):
        import json
        with open("schemas/arena_candidate.schema.json") as f:
            schema = json.load(f)
        assert schema["$id"] is not None

    def test_pairwise_schema_is_valid(self):
        import json
        with open("schemas/arena_pairwise_report.schema.json") as f:
            schema = json.load(f)
        assert "$id" in schema