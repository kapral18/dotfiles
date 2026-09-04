# Multi source claims

## Multi-source claim branch

Use this branch for comparisons, landscape research, papers, benchmarks, pricing, or any synthesis whose answer depends on multiple public factual claims.

### 1. Collect candidate claims

Keep claims atomic. For every candidate record:

- entity or subject
- one factual claim
- primary-source URL
- exact supporting quote
- finder identity and model family, when available

Every numeric literal in the claim must occur verbatim in that quote. No primary URL or exact quote means the claim remains unverified.
Reject the claim, not the entity or source. Done when every candidate has evidence or is explicitly unresolved.

### 2. Verify independently

A finder never verifies its own claim. Give a separate agent or fresh isolated context the claim and source, without the finder's rationale.
The verifier reopens the primary source, checks the quote and every number, and returns one verdict:

- `verified` — the primary source supports the claim as written
- `refuted` — the source contradicts or does not contain the claim
- `undecidable` — name the exact missing source or check

Use a different model family when the runtime exposes one. Otherwise use a distinct fresh agent and report `same-family (degraded)`.
If no independent context is available, keep the claim `undecidable`; do not relabel it verified.
Done when no candidate is awaiting a verifier.

### 3. Deepen, then synthesize

Deepening goes last. Give the deepening pass only verified claims plus the remaining gap list.
Any new claim from deepening returns to candidate collection and independent verification.
The final synthesis may use verified claims only; list unresolved gaps separately.
Done when every statement in the synthesis maps to a verified claim.

### 4. Persist selectively

Only verified claims may enter `,ai-kb`.
Store the primary URL in `--source`, include the exact quote in the body, identify the verifier with `--verified-by`, and set confidence honestly.
Refuted and undecidable claims remain task context, not durable knowledge.

Output:

- a compact claim table: claim, status, primary source, verifier
- synthesis based only on verified claims
- refuted claims and unresolved gaps, when material
