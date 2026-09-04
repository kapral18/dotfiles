---
name: k-ai-kb
description: "Use for non-trivial repo/domain starts, setup gotchas, or storing verified learnings in ,ai-kb."
---

# AI Knowledge Base Skill

Durable, structured, cross-session memory shared across agents (cursor-cli, pi, local sessions).
Backed by the local `,ai-kb` CLI: SQLite + FTS5 (BM25) + dense embeddings (`sqlite-vec`), RRF-fused and MMR-diversified.
Fully local, no cloud, no MCP. Capsules persist under `~/.local/share/ai-kb/` (markdown sidecars + indexed SQLite mirror).

Do not use:

- ephemeral per-session working context (current task spec, hook worklog/evidence trace under `/tmp/specs`):
  that is `,agent-memory` (see `~/.local/share/chezmoi/docs/topics/ai-assistants/knowledge-base/hook-memory.md`);
  this skill is for durable knowledge only
- semantic CODE search over a repo (how a codebase works, base-branch context): `~/.agents/skills/k-semantic-code-search/SKILL.md`
- simple string/filename lookup: local `rg` / file reads

k-agent-smol owns the KB boundary:

`,ai-kb` stays the only persistence layer; the `k-agent-smol` subagent (category `memory`, contract `~/.agents/skills/k-ai-kb/references/smol-operator.md`) operates both directions of its boundary so search dumps, candidate dumps, and write mechanics never occupy the parent context.
The parent MUST NOT run `,ai-kb search`, `,ai-kb get`, or `,ai-kb remember` inline;
inline runs exist only inside the no-spawn fallback below.

- Recall, on demand: when prior knowledge could help — starting non-trivial work, or hitting a likely known setup gotcha —
  delegate a recall query to `k-agent-smol` (judge mode, query-recall variant).
  Packet: the concrete task query, plus the session key and topic spec/worklog paths when the session has them.
  Fold in only the returned lines; `NONE` means inject nothing.
- Recall, staged per turn: the recall hook stages candidates to `/tmp/specs/<workspace>/.recall-candidates-<session-key>.json` and injects a pointer line, never capsule bodies.
  On seeing that pointer, delegate judgment to `k-agent-smol` (judge mode) with the candidates path, the topic spec/worklog paths, and the current prompt.
  Fold in only the lines it returns; `NONE` means inject nothing. Do not read the candidates file into the parent context.
- Write path: after verifying an insight in-session, delegate persistence to `k-agent-smol` (scribe mode) with the one-line insight, evidence anchors, and suggested kind/scope. k-agent-smol owns search-first dedupe, `--supersedes`, metadata selection, and read-back of the stored id.
  Persist only insights that are durable, reusable, and verified this session;
  never guesses or session-only notes (those belong in `,agent-memory`).
- Generic-spawn fallback: when the harness's native subagent surface cannot reach the `k-agent-smol` profile (fixed subagent set), spawn a generic isolated subagent type that can run shell commands, with the memory-category model set explicitly and a prompt that loads the operator contract; the isolation guarantee holds.
  Prefer a background spawn when the subagent surface supports one (e.g. Cursor Task `run_in_background: true`):
  launch the judge at pointer time, keep working, and fold in its returned lines when it completes.
  On Cursor that is `Task` with `subagent_type: shell` and `model: auto` (`shell` stays unbound in the band projection, so the explicit model survives the gate).
  Never spawn judge/scribe work on the subagent type's own default or banded model.
  Harness-CLI print/exec one-shots (`--print`, `exec`, `-p`) are an external mechanism, not part of this flow;
  do not use them for judge/scribe work.
- Inline fallback: only when no isolated spawn exists at all, load `~/.agents/skills/k-ai-kb/references/cli.md` and apply the operator contract yourself; the judge/scribe rules bind regardless of who executes them.

Harvest (opt-in candidate aid, not a substitute for the end-of-turn capture habit):

`,ai-kb harvest` mines a session-bound topic's hook worklog and prints durable-memory CANDIDATES —
a failing command later fixed, a recurring error signature, or a repeated command —
each with evidence and a prefilled `,ai-kb remember` line.
It is read-only and never writes a capsule: verify each candidate against live source, then hand the survivors to the scribe path (or run their `remember` lines in the inline fallback).
Run it on demand (for example when reviewing a long session), not every turn:
`,ai-kb harvest --session-id <id> [--topic <t>] [--worklog <path>] [--json]`.
Pass the invoking session ID when harvesting implicit topic state; an explicit `--topic` or `--worklog` overrides session resolution.
Candidates already covered by a capsule are suppressed automatically.

External truth:

- The full search/get/remember interface, field-selection rules, and output contract live in `~/.agents/skills/k-ai-kb/references/cli.md`.
  Resolve the live interface from the binary (`,ai-kb --help`, subcommand `--help`) rather than memory; the binary wins on conflict.
