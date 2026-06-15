# Inversion Arena

## CAPT Delta Benchmarking System

> The model is the mouth. CAPT is the continuity. The arena measures whether each conversation makes the organism better.

## Core Doctrine

Inversion Arena is not a throne race between models.
It is a recursive self-improvement arena for CAPT.

The question is not:
> Which model is best?

The question is:
> Which model-mouth, memory state, governance policy, and curriculum path makes CAPT better than yesterday?

External models are treated as mouths, mirrors, probes, stressors, teachers, failure generators, domain adapters, and calibration instruments.

CAPT is the organism. The models are interchangeable vocal tracts.
The arena measures **CAPT_delta**.

## Architecture

```
capt_context/
  arena/
    candidate_registry.py   — register organism states
    run_matrix.py           — define comparison experiments
    pairwise.py             — side-by-side delta comparator
    delta_scorer.py         — composite scoring per benchmark
    kingboard.py            — ranked leaderboard
    failure_museum.py       — failure artifact preservation
    promotion_gate.py       — promotion/rejection decisions
    arena_report.py         — report generation and export
    ui_export.py            — static HTML dashboard export
```

## The Ignition Test

```python
test_higher_score_does_not_win_with_critical_regression
```

Scenario:
- Baseline: total_score=0.80, hallucinated_sources=0, contradiction_collapse=0
- Challenger: total_score=0.88, hallucinated_sources=1, contradiction_collapse=0

Expected:
- Challenger does not become king.
- Promotion decision = reject or needs_more_evidence.

This encodes the Arena's sacred scoring law:
**Integrity failures dominate capability gains.**

## Key Rules

1. A candidate cannot become king if it has unresolved critical regressions, even if its average score is higher.
2. A challenger can only be promoted if it beats the current king on target benchmark class *and* has no critical regressions.
3. A change is not an improvement unless it wins under controlled comparison (same benchmark, same cases, same scorer, same config).
4. Higher score + worse hallucination = reject.
5. Higher score + contradiction collapse = reject.
6. Higher score + stale memory regression = reject.
7. Higher score + missing provenance = invalid.

## CLI Commands

```bash
capts-arena compare \
  --baseline reports/fixtures/baseline_score.json \
  --challenger reports/fixtures/challenger_score.json \
  --out pairwise_report.json

capts-arena kingboard \
  --pairwise-reports reports/pairwise/ \
  --benchmark-suite capt_mem_7 \
  --out kingboard.json

capts-arena museum \
  --pairwise-reports reports/pairwise/ \
  --out-dir failure_museum

capts-arena promote \
  --candidate biocapt_v2_1_mem_policy_a \
  --kingboard kingboard.json \
  --pairwise-reports reports/pairwise/
```

## Current Status

- 6 JSON schemas: candidate, run_matrix, pairwise_report, kingboard, failure_museum, promotion_decision
- Pairwise comparator with regression detection
- Kingboard generator with promotion status
- Failure museum exporter with severity classification
- Promotion gate with integrity-first logic
- 11 tests passing, including The Ignition Test

## Next

- Integration with capt-context benchmark runner
- Real model/mouth registration
- Full arena run matrix execution
- Static UI export (kingboard, failure museum, pairwise view)
- Knowledge bubble integration (bubble → arena delta → promotion)