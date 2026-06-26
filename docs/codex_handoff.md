# Codex Handoff: Finish the Inversion Arena

## Mission

Turn `capts-arena` into the full delta-benchmarking and recursive self-improvement system for CAPT, bioCAPT, and FrankenCAPT.

## Non-negotiables

- No fake benchmark results.
- No secrets or private traces in public commits.
- Every promotion decision must be explainable from pairwise reports.
- Every critical regression must become a failure museum artifact.
- Higher fluency never overrides hallucination, unsupported claims, stale memory, contradiction collapse, or governance failure.

## Immediate implementation tasks

1. Wire private benchmark output into the report-file matrix contract.
2. Add signed run manifests:
   - benchmark hash
   - candidate hash
   - scorer version
   - runner version
   - environment digest
3. Add persistent kingboard history:
   - previous king
   - challenger
   - promotion decision
   - reason
   - linked pairwise reports
4. Add failure museum replay:
   - export museum entry as benchmark case
   - rerun repaired candidate against original failure
5. Add a minimal static Arena UI:
   - kingboard table
   - candidate cards
   - failure museum index
   - pairwise diff view
6. Add schema validation in CI.
7. Keep private benchmark suites and raw logs outside this public repo.

## Production readiness criteria

- `pytest` passes.
- Example matrix produces pairwise reports, kingboard, museum entries, and promotion decisions.
- Missing reports fail hard.
- Critical regression test passes.
- No hard-coded local paths.
- No placeholder benchmark results.
