---
name: ai-kb
description: "Durable cross-session agent memory via the local ,ai-kb CLI (hybrid BM25 + vector + RRF + MMR, no cloud). Use to recall prior learnings, gotchas, decisions, and patterns before working, and to remember durable, reusable insights after verifying them. Not for ephemeral /tmp/specs working context (,agent-memory) or code search (semantic-code-search)."
---

# AI Knowledge Base Skill

Durable, structured, cross-session memory shared across agents (cursor-cli, pi, Ralph). Backed by the local `,ai-kb` CLI: SQLite + FTS5 (BM25) + dense embeddings (`sqlite-vec`), fused with Reciprocal Rank Fusion and diversified with Maximal Marginal Relevance. Fully local, no cloud, no MCP. Capsules persist under `~/.local/share/ai-kb/` (markdown sidecars + indexed SQLite mirror).

Use when:

- starting non-trivial work in a repo/domain: recall prior gotchas, decisions, patterns, and verified facts before acting
- you hit a problem the setup likely encountered before (build quirk, tool flag, env constraint)
- you have just verified a durable, reusable insight worth carrying to future sessions and other agents

Do not use:

- ephemeral per-session working context (current task spec, worklog, evidence ledger under `/tmp/specs`): that is `,agent-memory` (see `~/.local/share/chezmoi/docs/topics/ai-assistants/knowledge-base.md`); this skill is for durable knowledge only
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

- Only `,ai-kb remember` an insight that is durable and reusable, and that you have verified in this session (External Truth applies — do not store guesses).
- Make it specific and reusable; do not restate the task goal. Mirror the quality bar of a good `LEARNING:` line.

```bash
,ai-kb remember --title "<short specific title>" --body "<the reusable insight>" \
  --kind gotcha --scope project --workspace "$(pwd)" --tags "<csv>" --domain "<tag>"
```

- Choose `--kind` honestly: `gotcha` (trap/surprise), `anti_pattern` (what not to do), `pattern`/`recipe` (reusable approach), `principle` (rule), `fact` (verified state), `doc` (reference chunk).
- Choose `--scope` by reuse breadth: `workspace` (this checkout), `project` (this project across worktrees), `domain` (a tech/topic across projects), `universal` (everywhere).
- `--domain` is repeatable on `remember` (pass it multiple times for multiple tags).
- Verifying agents may set `--confidence <0..1>` and `--verified-by <ref>` when raising trust in an existing insight's restatement.
- Do not pollute the KB: skip transient, session-only, or unverified notes (those belong in `,agent-memory`).

Output:

- `--json` returns an array of hits. Each hit carries: `id`, `title`, `body`, `snippet`, `source`, `tags`, `kind`, `scope`, `workspace_path`, `domain_tags`, `confidence`, ranking fields (`bm25_rank`, `vector_rank`, `bm25_score`, `cosine_score`, `rrf_score`, `mmr_selected`).
- Fold the most relevant hits into your reasoning and cite them by `title` (and `id` when acting on one). Treat low-`confidence` or superseded-looking hits with caution; verify against the live repo before relying on them.
- Superseded capsules are excluded from results by default; results are already RRF-ranked and MMR-diversified — do not re-sort.

External truth:

- Resolve the live interface from the binary (`,ai-kb --help`, `,ai-kb remember --help`, `,ai-kb search --help`) rather than memory; flags and enums are the source of truth.
