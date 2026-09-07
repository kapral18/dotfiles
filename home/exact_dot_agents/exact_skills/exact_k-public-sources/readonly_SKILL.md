---
name: k-public-sources
description: "Use when inspecting external public repos from source or verifying factual claims across public sources."
---

# Public Sources

Choose the smallest branch that answers the question:

- **Source-inspection branch:** resolve the right upstream/ref, then inspect source locally.
- **Multi-source claim branch:** collect factual claims, independently verify them, then deepen and synthesize.

Explicit repo/file/directory URLs use the source-inspection branch.

Do not use:

- for the current repo/worktree you are already in
- when the authoritative answer is product/account/runtime state rather than public source
- for a single-page web lookup that needs neither source inspection nor multi-source synthesis

Delegation (SOP §3.7 `research` dispatch gate; children are leaf workers and cannot spawn):

- Source-inspection branch: the whole clone-and-inspect runs in one isolated `k-agent-public-sources` child (OMP, Pi, Claude) —
  it loads `~/.agents/skills/k-review/references/public-sources.md` — or, where that profile is unreachable, in the harness's `research`-bound native explorer / generic type with the registry `research` model passed explicitly and the same contract in the prompt.
  The root session MUST NOT clone or grep the external repo itself; it receives the answer, repo, and exact ref.
- Multi-source claim branch: the root stays coordinator and dispatches each phase of `multi-source-claims.md` as its own leaf packet —
  (1) candidate collection on `k-agent-public-sources`, (2) one independent verification packet per claim (claim + source only, never the finder's rationale) on `k-agent-claim-verifier` (OMP, Pi, Claude; loads `references/claim-verifier.md` on the `refute` band), else a fresh generic child on the registry `refute` model with that contract in the prompt; report `same-family (degraded)` when no second family exists, (3) deepening/synthesis on `k-agent-public-sources` with verified claims and the gap list only.
  The root MUST NOT hand the entire multi-source workflow to one child, and MUST NOT collect or verify claims itself;
  it judges the returned claim table.

## Source-inspection branch

Before performing this branch, read and follow `~/.agents/skills/k-public-sources/references/source-inspection.md` in full.

## Multi-source claim branch

Use this branch for comparisons, landscape research, papers, benchmarks, pricing, or any synthesis whose answer depends on multiple public factual claims.
Before collecting, verifying, deepening, or synthesizing those claims, read and follow `~/.agents/skills/k-public-sources/references/multi-source-claims.md` in full.
