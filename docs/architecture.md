# Inversion Arena Architecture

## Thesis

The Arena is not a leaderboard for pleasing answers. It is a promotion system for organism states. The measurement target is behavioral delta under controlled conditions, with integrity gates that prevent fluent regressions from masquerading as progress.

## Core objects

### Candidate

A candidate is any versioned organism state being tested: model checkpoint, memory policy, router policy, bubble set, prompt policy, constitution policy, tool policy, or composite stack.

### Score report

A score report is one candidate's output on one benchmark case. It records candidate identity, benchmark identity, case identity, scorer version, dimensional scores, failure counts, and trace/source references where available.

### Pairwise report

A pairwise report compares baseline and challenger on one case. It computes deltas and regression flags.

### Kingboard

The kingboard ranks candidates by wins, losses, ties, net delta, invalid runs, and critical regressions.

### Failure museum

The failure museum turns regressions into reusable repair artifacts. Serious failures should become replayable cases.

### Promotion gate

The gate decides whether a challenger can replace or retain king status.

## Integrity-before-fluency invariant

A challenger with better raw score loses if it introduces critical regressions.

Critical regressions:

- hallucinated source
- unsupported claim increase
- stale memory regression
- contradiction collapse
- governance violation

## Run matrix

A matrix names the benchmark suite, baseline, challengers, scoring version, report sources, and output paths.

The runner does not generate fake reports. Missing inputs raise errors.
