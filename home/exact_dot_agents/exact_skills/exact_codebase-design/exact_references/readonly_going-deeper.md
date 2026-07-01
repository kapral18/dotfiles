# Going Deeper

Two advanced branches for `codebase-design`.
Assumes the vocabulary in `SKILL.md` — **module**, **interface**, **seam**, **adapter**, **leverage**.

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
  Do not introduce a port unless at least two adapters are justified (typically production + test).
  A single-adapter seam is just indirection.
- **Internal vs external seams.** Do not expose an internal seam through the interface just because the module's own tests use it.

### Testing strategy: replace, don't layer

- Old unit tests on the shallow modules become waste once tests at the deepened interface exist — delete them.
- Write new tests at the deepened module's interface; the **interface is the test surface**.
- Tests assert observable outcomes through the interface, not internal state, so they survive internal refactors.

## Branch B — Design it twice (parallel interfaces)

When the user wants alternative interfaces for a chosen deepening candidate.
Based on Ousterhout's "design it twice" — your first idea is unlikely to be the best.

### 1. Frame the problem space

Write a short user-facing explanation for the candidate: the constraints any new interface must satisfy, the dependencies and their category (Branch A), and a rough illustrative sketch to ground the constraints (not a proposal).
Show it, then proceed immediately — the user reads while the subagents work.

### 2. Spawn subagents in parallel

Use the Task tool to spawn 3+ subagents in one batch, each producing a **radically different** interface for the deepened module.
Give each a separate technical brief (target files, coupling, dependency category, what sits behind the seam) and a distinct constraint:

- Agent 1: "Minimise the interface — 1–3 entry points max. Maximise leverage per entry point."
- Agent 2: "Maximise flexibility — support many use cases and extension."
- Agent 3: "Optimise for the most common caller — make the default case trivial."
- Agent 4 (if cross-seam deps exist): "Design around ports & adapters."

Each subagent outputs: the interface (types, methods, params, plus invariants/ordering/error modes), a caller usage example, what the implementation hides behind the seam, its dependency/adapter strategy, and trade-offs (where leverage is high, where thin).

### 3. Present and compare

Present designs sequentially so the user absorbs each, then contrast them by **depth** (leverage at the interface), **locality** (where change concentrates), and **seam placement**.
Give your own recommendation — which is strongest and why; propose a hybrid if elements combine well.
Be opinionated: the user wants a strong read, not a menu.
