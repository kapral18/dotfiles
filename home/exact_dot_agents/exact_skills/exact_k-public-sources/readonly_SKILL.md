---
name: k-public-sources
description: "Use when inspecting external public source or synthesizing evidence across sources."
---

# Public Sources

Subagent dispatch: research (refute for the batched claim set) — one research packet per independent question.

Use source-inspection for explicit upstream repositories/files; use multi-source claims for factual synthesis across sources.
This skill provides evidence mechanics, not a collect→verify→deepen loop.
Do not use it for the current worktree, account/runtime state, or a simple single-page lookup.
For source inspection, read `~/.agents/skills/k-public-sources/references/source-inspection.md`.
For multi-source synthesis, read `~/.agents/skills/k-public-sources/references/multi-source-claims.md`.

## Root moves

Only the active root/main session follows this section; a delegated leaf skips it and returns findings to its parent.
Launch one strong research packet per independent question, combining collection and synthesis; the root MUST NOT substitute its own inline investigation for that packet absent an explicit user no-delegation instruction; if the lane is unavailable report blocked.
Keep raw source outside root context; return evidence pointers, supported conclusions, and unresolved gaps.
For multi-source synthesis, read `~/.agents/skills/k-public-sources/references/claim-verifier.md` and judge the material claim set together in final Verify.
Assign that contract to a strong refute packet when the set holds two or more independent claims or any claim gates a decision; the root judges inline only under an explicit user no-delegation instruction; do not spawn a verifier per claim or send new claims into recursive deepening.
Resolve capability/model/effort through the registry; report reduced independence for same-family or inline judgment.
Honor no-delegation requests inline.
