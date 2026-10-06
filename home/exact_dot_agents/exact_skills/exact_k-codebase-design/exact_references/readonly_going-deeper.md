# Going Deeper

Two advanced branches for `k-codebase-design`.
Assumes the vocabulary in `~/.agents/skills/k-codebase-design/SKILL.md` — **module**, **interface**, **seam**, **adapter**, **leverage**.

## Branch A — Deepening a cluster given its dependencies

Classify a candidate's dependencies first; the category determines how the deepened module is tested across its seam.

1. **In-process** — pure computation, in-memory state, no I/O.
   Always deepenable: merge the modules, test through the new interface directly. No adapter needed.
2. **Local-substitutable** — dependencies with local test stand-ins (PGLite for Postgres, in-memory filesystem).
   Deepenable if the stand-in exists; test with it running in the suite. The seam is internal; no port at the external interface.
3. **Remote but owned (ports & adapters)** — your own services across a network boundary.
   Define a **port** at the seam; the deep module owns the logic, the transport is an injected **adapter**.
   Tests use an in-memory adapter; production uses HTTP/gRPC/queue.
4. **True external (mock)** — third-party services you do not control. Inject the dependency as a port; tests provide a mock adapter.

### Seam discipline

- **One adapter = hypothetical seam. Two = real.**
  Introduce a port only when at least two adapters are justified (typically production + test). A single-adapter seam is just indirection.
- **Internal vs external seams.**
  Keep internal seams private to the implementation even when the module's own tests use them;
  expose a seam through the interface only for external callers.

### Testing strategy: replace, don't layer

- Old unit tests on the shallow modules become waste once tests at the deepened interface exist — delete them.
- Write new tests at the deepened module's interface; the **interface is the test surface**.
- Tests assert observable outcomes through the interface, not internal state, so they survive internal refactors.

## Branch B — Design it twice (alternative interfaces)

When the user wants alternative interfaces for a chosen deepening candidate.
Based on Ousterhout's "design it twice" — your first idea is unlikely to be the best.

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
