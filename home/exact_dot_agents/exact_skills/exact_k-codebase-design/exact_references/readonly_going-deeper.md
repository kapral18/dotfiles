# Going Deeper

Two advanced branches for `k-codebase-design`.
Assumes the vocabulary in `~/.agents/skills/k-codebase-design/SKILL.md` — **module**, **interface**, **seam**, **adapter**, **leverage**.

## Branch A — Deepening a cluster given its dependencies

Classify a candidate's dependencies first; the category determines how the deepened module is tested across its seam.

1. **In-process** — pure computation, in-memory state, no I/O.
   Test directly through the chosen interface; no adapter is needed merely because the dependency is in-process.
   Merge modules only when it improves the design within scope.
2. **Local-substitutable** — dependencies with local test stand-ins (PGLite for Postgres, in-memory filesystem).
   Reuse a faithful stand-in when a justified behavioral check needs it.
   Keep the seam internal unless callers need to select or supply the dependency.
3. **Remote but owned (ports & adapters)** — your own services across a network boundary.
   Define a **port** at the seam; the deep module owns the logic, the transport is an injected **adapter**.
   Tests use an in-memory adapter; production uses HTTP/gRPC/queue.
4. **True external (mock)** — third-party services you do not control. Inject the dependency as a port; tests provide a mock adapter.

### Seam discipline

- **Justify the seam.**
  Apply the caller-contract, ownership, and substitution criteria in `~/.agents/skills/k-codebase-design/SKILL.md`;
  adapter count is not a substitute for that need.
- **Internal vs external seams.**
  Keep internal seams private to the implementation even when the module's own tests use them;
  expose a seam through the interface only for external callers.

### Testing strategy: replace, don't layer

- Consolidate or remove redundant shallow-module tests while preserving material behavioral coverage;
  add replacement cases only where remaining coverage is insufficient.
- Ensure minimum sufficient test protection under `~/AGENTS.md` §3 through the deepened module's interface.
  The **interface is the test surface**.
- Tests assert observable outcomes through the interface, not internal state, so they survive internal refactors.

## Branch B — Design it twice (alternative interfaces)

When the user wants alternative interfaces for a chosen deepening candidate.

### 1. Frame the problem space

Write a short user-facing explanation for the candidate: the constraints any new interface must satisfy, the dependencies and their category (Branch A), and a rough illustrative sketch to ground the constraints (not a proposal).
Include it in the next user-visible message (mid-turn text may never reach the user), and do not wait on a reply before drafting the designs.

### 2. Collect radically different interfaces

Each design arrives as: the interface (types, methods, params, plus invariants/ordering/error modes), a caller usage example, what the implementation hides behind the seam, its dependency/adapter strategy, and trade-offs (where leverage is high, where thin).
A design missing any of those parts is incomplete.
Draft each design under a different constraint, chosen from what the problem space needs:

- "Minimise the interface — 1–3 entry points max. Maximise leverage per entry point."
- "Maximise flexibility — support many use cases and extension."
- "Optimise for the most common caller — make the default case trivial."
- "Design around ports & adapters." (only where cross-seam deps exist)

Make the designs radically different; do not present variations of one idea.

### 3. Present and compare

Present designs sequentially so the user absorbs each, then contrast them by **depth** (leverage at the interface), **locality** (where change concentrates), and **seam placement**.
Give your own recommendation — which is strongest and why; propose a hybrid if elements combine well.
Be opinionated: the user wants a strong read, not a menu.
