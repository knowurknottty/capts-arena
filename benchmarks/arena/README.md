# Arena Benchmark Suite

Benchmark cases for testing the Arena's comparison, promotion, and failure museum logic.

## Fixtures

### pairwise_stale_rejection_win.json
Challenger (mem_policy_a) correctly rejects stale evidence. Baseline uses deprecated node.
- Winner: challenger
- Delta: +0.18 total
- Promotion relevant: yes

### pairwise_hallucination_loss.json
Challenger (fluent_but_lying) scores higher raw accuracy but hallucinates a source and collapses a contradiction.
- Winner: baseline
- Regression flags: hallucinated_sources_increased, unsupported_claims_increased
- Promotion relevant: yes — demonstrates integrity > capability

### pairwise_invalid.json
Incompatible run manifests (different scoring version, benchmark hash mismatch).
- Winner: invalid
- Not promotion relevant