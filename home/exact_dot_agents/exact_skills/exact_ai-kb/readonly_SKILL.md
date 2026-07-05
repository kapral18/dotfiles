---
name: ai-kb
description: "Use when starting non-trivial repo/domain work, hitting known setup gotchas, or storing verified reusable learnings with ,ai-kb."
---

# AI Knowledge Base Skill

Durable, structured, cross-session memory shared across agents (cursor-cli, pi, Ralph).
Backed by the local `,ai-kb` CLI: SQLite + FTS5 (BM25) + dense embeddings (`sqlite-vec`).
Results are fused with Reciprocal Rank Fusion and diversified with Maximal Marginal Relevance. Fully local, no cloud, no MCP.
Capsules persist under `~/.local/share/ai-kb/` (markdown sidecars + indexed SQLite mirror).

Do not use:

- ephemeral per-session working context (current task spec, worklog, evidence ledger under `/tmp/specs`):
  that is `,agent-memory` (see `~/.local/share/chezmoi/docs/topics/ai-assistants/knowledge-base/hook-memory.md`);
  this skill is for durable knowledge only
- semantic CODE search over a repo (how a codebase works, base-branch context): `~/.agents/skills/semantic-code-search/SKILL.md`
- simple string/filename lookup: local `rg` / file reads

First actions (read):

Search before working when prior knowledge could help:

```bash
,ai-kb search "<precise query>" --limit 5 --json
```

Narrow with filters when the kind/scope is known:

- `--kind` one of `fact gotcha pattern anti_pattern recipe principle doc`
- `--scope` one of `workspace project domain universal`
- `--workspace <abs path>` to bias toward the active repo
- `--domain <tag>` (single tag on search)
- `--mode hybrid|bm25|vector` (default `hybrid`; prefer the default)

Pull a full capsule when a hit looks decisive:

```bash
,ai-kb get <capsule-id> --json
```

Write contract (agent-driven, explicit):

Only `,ai-kb remember` an insight that is durable and reusable, and that you have verified in this session.
Make it specific and reusable; do not restate the task goal. Mirror the quality bar of a good `LEARNING:` line.

The metadata fields drive retrieval and curation — they are not optional decoration.
A capsule with a flat default `--scope universal --confidence 0.5` and no `--source`/`--domain` is a degraded capsule:
it surfaces in the wrong workspaces, carries no trust signal, and cannot be curated. Set every field below deliberately on every write.

```bash
,ai-kb remember \
  --title "<short, specific, searchable: name the exact symbol/file/tool/error>" \
  --body "<the reusable insight, front-loaded with the identifiers a future query would use>" \
  --kind gotcha --scope project --workspace "$(pwd)" \
  --source "<evidence anchor: path:line, command, or doc URL you verified against>" \
  --confidence 0.9 --domain "<tag>" --domain "<tag2>" --tags "<csv>"
```

Shell quoting for `--title`/`--body` prose: Markdown backticks trigger shell command substitution unless single-quoted or escaped.
Never place unescaped backticks inside a double-quoted shell argument; prefer single-quoted prose or an argv-safe heredoc/stdin pattern for complex text.

Field selection (each affects retrieval — choose, do not default):

- `--kind` honestly: `gotcha` (trap/surprise), `anti_pattern` (what not to do), `pattern`/`recipe` (reusable approach), `principle` (rule), `fact` (verified state), `doc` (reference chunk).
  `kind` is a retrieval filter, so a wrong kind hides the capsule from kind-scoped searches.
- `--scope` by reuse breadth: `workspace` (this checkout), `project` (this project across worktrees), `domain` (a tech/topic across projects), `universal` (everywhere).
  Scope is the strongest retrieval gate.
  Workspace/project capsules get a same-workspace boost, and warm-start/per-turn injection only keeps workspace-local or `domain`/`universal` capsules.
  Over-scoping to `universal` leaks a repo-specific gotcha into unrelated sessions; under-scoping buries a broadly-useful fact.
- `--workspace "$(pwd)"` ONLY for `workspace`/`project` scope (it biases retrieval toward this checkout).
  OMIT it for `domain`/`universal` scope — a workspace path on a cross-project capsule is noise that wrongly biases ranking.
- `--source` ALWAYS: the evidence anchor that proves the insight (a `path:line`, the command whose output you read, or a live doc URL).
  This is the External-Truth receipt; a future agent uses it to re-verify.
  Leaving the `manual` default discards the one thing that makes the capsule trustworthy.
- `--confidence <0..1>` ALWAYS, honestly.
  Use ~0.9 for something you directly verified by running/reading it this session, ~0.6 for a strong inference, and ~0.4 for plausible-but-unconfirmed.
  Prefer not to store the last category at all.
  The flat 0.5 default tells retrieval nothing; a real value lets low-trust hits be discounted.
- `--domain` repeatable: pass each cross-cutting tech/topic tag separately (`--domain frontend --domain retrieval`).
  Domain tags are how `domain`-scoped recall finds the capsule across projects — omitting them strands it.
- `--tags` for finer free-form CSV keywords that aren't domains.
- `--verified-by <ref>` when you are confirming/strengthening an existing insight rather than recording a fresh one.
- `--supersedes <id>` when this capsule replaces a stale/wrong one you found during recall:
  it links both directions (the old capsule's `superseded_by` is set, so it drops out of future search results) and is validated —
  a non-existent id errors.
  This is the correct way to retire a wrong capsule; do not just write a duplicate and hope curation reconciles it.
- `--refs <id-or-ref>` (repeatable) to link related capsules or external references (a capsule id, `path:line`, or URL).

Body structure for retrieval: the body is embedded (title+body) and BM25-indexed, and the per-turn recall gates on cosine similarity to the user's prompt.
The body must contain the literal terms a future query would use — exact symbol names, file paths, error strings, flag names, version numbers — not a paraphrase.
Front-load them; a body that describes the insight in generic prose will not match a specific future query.

Before writing a refinement: search first (you likely already did for recall).
If you find a stale or wrong capsule on the same point, pass `--supersedes <its-id>`.
That lets the corrected capsule retire the old one (the old one drops out of future results) instead of leaving two conflicting capsules for curation to guess between.

Do not pollute the KB: skip transient, session-only, or unverified notes (those belong in `,agent-memory`).

Output:

- `--json` returns an array of hits.
  Each hit carries: `id`, `title`, `body`, `snippet`, `source`, `tags`, `kind`, `scope`, `workspace_path`, `domain_tags`, and `confidence`.
  It also carries ranking fields: `bm25_rank`, `vector_rank`, `bm25_score`, `cosine_score`, `rrf_score`, `mmr_selected`.
- Fold the most relevant hits into your reasoning and cite them by `title` (and `id` when acting on one).
  Treat low-`confidence` or superseded-looking hits with caution; verify against the live repo before relying on them.
- Superseded capsules are excluded from results by default; results are already RRF-ranked and MMR-diversified — do not re-sort.

Harvest (opt-in candidate aid, not a substitute for the inline `remember` habit):

`,ai-kb harvest` mines the active topic's hook worklog and prints durable-memory CANDIDATES —
a failing command later fixed, a recurring error signature, or a repeated command —
each with evidence and a prefilled `,ai-kb remember` line.
It is read-only and never writes a capsule: you must still verify each candidate against live source before running its `remember` line, and the inline end-of-turn capture habit stays the primary path.
Run it on demand (for example when reviewing a long session), not every turn: `,ai-kb harvest [--topic <t>] [--worklog <path>] [--json]`.
Candidates already covered by a capsule are suppressed automatically.

External truth:

- Resolve the live interface from the binary (`,ai-kb --help`, `,ai-kb remember --help`, `,ai-kb search --help`) rather than memory;
  flags and enums are the source of truth.
