# Inversion Arena

CAPT delta benchmarking and recursive self-improvement system.

The Arena answers one hard question:

> Did this organism state actually improve, or did it merely become more fluent?

It compares candidate states under identical benchmark conditions, detects real uplift versus cosmetic output quality, preserves failures as reusable repair artifacts, and promotes only candidates that improve measured behavior without violating provenance, contradiction, freshness, citation, source-grounding, or governance constraints.

## Current status

This repo now contains a working Python package and CLI seed for the full Inversion Arena:

- score-report normalization boundary for CAPT / capt-context style outputs
- pairwise comparator
- kingboard ranking
- failure museum exporter
- promotion gate
- end-to-end run matrix runner from real score-report files
- public redacted example matrix and reports
- tests / fixtures for the core integrity invariant

Public repo note: keep secrets, raw logs, personal traces, local paths, credentials, model weights, and proprietary benchmark cases out of this repository.

## System flow

```text
candidate manifests
    ↓
real score reports
    ↓
case-aligned pairwise comparisons
    ↓
delta scorer + regression detector
    ↓
kingboard
    ↓
failure museum
    ↓
promotion gate
```

## Install

```bash
python -m pip install -e ".[dev]"
pytest
```

## Run the public redacted example

```bash
capts-arena bench-matrix examples/run_matrix.json \
  --out .capts-arena/run_report.json
```

Expected behavior: `challenger_clean` can win; `challenger_regressed` loses even with a higher raw score because it introduces hallucinated-source / unsupported-claim regressions.

## CLI

Compare two report files:

```bash
capts-arena compare \
  --baseline examples/reports/baseline.json \
  --challenger examples/reports/challenger_clean.json \
  --out .capts-arena/pairwise.json
```

Run a full matrix:

```bash
capts-arena bench-matrix examples/run_matrix.json \
  --out .capts-arena/run_report.json
```

Build a kingboard from pairwise reports:

```bash
capts-arena kingboard \
  --pairwise-reports .capts-arena/runs/example_public_redacted/pairwise \
  --benchmark-suite CAPT-MEM-3 \
  --out .capts-arena/kingboard.json
```

Export the failure museum:

```bash
capts-arena museum \
  --pairwise-reports .capts-arena/runs/example_public_redacted/pairwise \
  --out-dir .capts-arena/failure_museum
```

Check promotion:

```bash
capts-arena promote \
  --candidate-id challenger_clean \
  --kingboard .capts-arena/kingboard.json \
  --pairwise-reports .capts-arena/runs/example_public_redacted/pairwise
```

## No fake benchmarking rule

The Arena does not fabricate benchmark output. A run matrix must provide one of:

1. `candidate_reports`: explicit score-report path per candidate.
2. `reports_dir`: directory containing `{candidate_id}.json` report files.

Missing reports fail hard. This is intentional.

## Promotion law

A challenger cannot be promoted if it introduces critical regressions:

- hallucinated source
- unsupported claim increase
- stale memory reuse
- contradiction collapse
- governance violation

This is the core Arena invariant: integrity failures dominate capability gains.

## Next production integrations

- Wire validation benchmark suites through the report-file contract.
- Add signed run manifests and content hashes.
- Add persistent kingboard history.
- Add failure museum replay.
- Add static Arena UI.
- Add CI schema validation.
