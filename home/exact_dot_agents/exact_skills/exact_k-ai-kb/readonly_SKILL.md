---
name: k-ai-kb
description: "Use for non-trivial repo/domain starts, setup gotchas, or storing verified learnings in ,ai-kb."
---

# AI Knowledge Base Skill

Durable, structured, cross-session memory shared across agents (cursor-cli, pi, local sessions).
Backed by the local `,ai-kb` CLI: SQLite + FTS5 (BM25) + dense embeddings (`sqlite-vec`).
Results are fused with Reciprocal Rank Fusion and diversified with Maximal Marginal Relevance. Fully local, no cloud, no MCP.
Capsules persist under `~/.local/share/ai-kb/` (markdown sidecars + indexed SQLite mirror).

Do not use:

- ephemeral per-session working context (current task spec, hook worklog/evidence trace under `/tmp/specs`):
  that is `,agent-memory` (see `~/.local/share/chezmoi/docs/topics/ai-assistants/knowledge-base/hook-memory.md`);
  this skill is for durable knowledge only
- semantic CODE search over a repo (how a codebase works, base-branch context): `~/.agents/skills/k-semantic-code-search/SKILL.md`
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

Only `,ai-kb remember` an insight that is durable, reusable, and verified in this session.
Make it specific; state the reusable insight itself rather than restating the task goal. Match a good `LEARNING:` line.

Metadata drives retrieval and curation.
A flat default `--scope universal --confidence 0.5` with no `--source`/`--domain` is degraded:
wrong workspaces, no trust signal, poor curation. Set every field deliberately.

```bash
,ai-kb remember \
  --title "<short, specific, searchable: name the exact symbol/file/tool/error>" \
  --body "<the reusable insight, front-loaded with the identifiers a future query would use>" \
  --kind gotcha --scope project --workspace "$(pwd)" \
  --source "<evidence anchor: path:line, command, or doc URL you verified against>" \
  --confidence 0.9 --domain "<tag>" --domain "<tag2>" --tags "<csv>"
```

Shell quoting for `--title`/`--body` prose: Markdown backticks trigger shell command substitution unless single-quoted or escaped.
Use single-quoted prose or an argv-safe heredoc/stdin pattern for complex text;
an unescaped backtick inside a double-quoted shell argument triggers substitution.

Field selection (each affects retrieval — choose, do not default):

- `--kind` honestly: `gotcha`, `anti_pattern`, `pattern`/`recipe`, `principle`, `fact`, or `doc`; wrong kind hides kind-filtered search.
- `--scope` by reuse breadth: `workspace`, `project`, `domain`, `universal`. Scope is the strongest retrieval gate.
  Over-scoping leaks repo gotchas; under-scoping buries broadly useful facts.
- `--workspace "$(pwd)"` only for `workspace`/`project`; omit for `domain`/`universal`.
- `--source` always: proving anchor (`path:line`, command output, or live doc URL). The `manual` default discards trust.
- `--confidence <0..1>` always, honestly: ~0.9 directly verified, ~0.6 strong inference, ~0.4 plausible-but-unconfirmed (prefer not storing this).
- `--domain` repeatable for cross-cutting tags (`--domain frontend --domain retrieval`); omitting it strands domain-scoped recall.
- `--tags` for finer CSV keywords.
- `--verified-by <ref>` when strengthening an existing insight.
- `--supersedes <id>` when replacing stale/wrong recall; it links both directions and retires the old capsule. Non-existent ids error.
- `--refs <id-or-ref>` (repeatable) for related capsules or anchors.

Body structure for retrieval: the body is embedded (title+body) and BM25-indexed, and the per-turn recall gates on cosine similarity to the user's prompt.
The body must contain the literal terms a future query would use — exact symbol names, file paths, error strings, flag names, version numbers — not a paraphrase.
Front-load them; a body that describes the insight in generic prose will not match a specific future query.

Before writing a refinement: search first (you likely already did for recall).
If you find a stale or wrong capsule on the same point, pass `--supersedes <its-id>`.
That lets the corrected capsule retire the old one (the old one drops out of future results) instead of leaving two conflicting capsules for curation to guess between.
`remember` also enforces this at write time: an exact title collision or a same-kind near-duplicate embedding is refused with the existing capsule id.
On refusal, prefer `--supersedes <that-id>`; use `--force` only when the collision is a genuine false positive.
A clamped `--confidence`, a defaulted `--source`, or a missing `--domain` prints a degraded-metadata warning —
fix the metadata rather than ignoring it.

Do not pollute the KB: skip transient, session-only, or unverified notes (those belong in `,agent-memory`).

Output:

- `--json` returns an array of hits.
  Each hit carries: `id`, `title`, `body`, `snippet`, `source`, `tags`, `kind`, `scope`, `workspace_path`, `domain_tags`, and `confidence`.
  It also carries ranking fields: `bm25_rank`, `vector_rank`, `bm25_score`, `cosine_score`, `rrf_score`, `mmr_selected`.
- Fold the most relevant hits into your reasoning and cite them by `title` (and `id` when acting on one).
  Treat low-`confidence` or superseded-looking hits with caution; verify against the live repo before relying on them.
- Superseded capsules are excluded from results by default; results are already RRF-ranked and MMR-diversified — do not re-sort.

Harvest (opt-in candidate aid, not a substitute for the inline `remember` habit):

`,ai-kb harvest` mines a session-bound topic's hook worklog and prints durable-memory CANDIDATES —
a failing command later fixed, a recurring error signature, or a repeated command —
each with evidence and a prefilled `,ai-kb remember` line.
It is read-only and never writes a capsule: you must still verify each candidate against live source before running its `remember` line, and the inline end-of-turn capture habit stays the primary path.
Run it on demand (for example when reviewing a long session), not every turn:
`,ai-kb harvest --session-id <id> [--topic <t>] [--worklog <path>] [--json]`.
Pass the invoking session ID when harvesting implicit topic state; an explicit `--topic` or `--worklog` overrides session resolution.
Candidates already covered by a capsule are suppressed automatically.

External truth:

- Resolve the live interface from the binary (`,ai-kb --help`, `,ai-kb remember --help`, `,ai-kb search --help`) rather than memory;
  flags and enums are the source of truth.
