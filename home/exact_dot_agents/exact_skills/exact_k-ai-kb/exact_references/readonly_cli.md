# `,ai-kb` CLI contract (runner-facing)

This is the interface for whoever actually runs the CLI: the `smol` operator by default, the parent session only inside the k-ai-kb no-spawn inline fallback.
Running these commands in a parent session outside that fallback breaks the isolation boundary the operator exists to hold.

## Read: search and get

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

Output:

- `--json` returns an array of hits.
  Each hit carries: `id`, `title`, `body`, `snippet`, `source`, `tags`, `kind`, `scope`, `workspace_path`, `domain_tags`, and `confidence`.
  It also carries ranking fields: `bm25_rank`, `vector_rank`, `bm25_score`, `cosine_score`, `rrf_score`, `mmr_selected`.
- Cite folded hits by `title` (and `id` when acting on one).
  Treat low-`confidence` or superseded-looking hits with caution; verify against the live repo before relying on them.
- Superseded capsules are excluded from results by default; results are already RRF-ranked and MMR-diversified — do not re-sort.

## Write: remember

Only `,ai-kb remember` an insight that is durable, reusable, and verified in the current session.
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

Body structure for retrieval: the body is embedded (title+body) and BM25-indexed;
per-turn recall stages candidates gated on cosine similarity to the user's prompt, and the smol judge admits only what the session state needs.
The body must contain the literal terms a future query would use — exact symbol names, file paths, error strings, flag names, version numbers — not a paraphrase.
Front-load them; a body that describes the insight in generic prose will not match a specific future query.

Before writing a refinement: search first. If you find a stale or wrong capsule on the same point, pass `--supersedes <its-id>`.
That lets the corrected capsule retire the old one (the old one drops out of future results) instead of leaving two conflicting capsules for curation to guess between.
`remember` also enforces this at write time: an exact title collision or a same-kind near-duplicate embedding is refused with the existing capsule id.
On refusal, prefer `--supersedes <that-id>`; use `--force` only when the collision is a genuine false positive.
A clamped `--confidence`, a defaulted `--source`, or a missing `--domain` prints a degraded-metadata warning —
fix the metadata rather than ignoring it.

Do not pollute the KB: skip transient, session-only, or unverified notes (those belong in `,agent-memory`).

## External truth

Resolve the live interface from the binary (`,ai-kb --help`, `,ai-kb remember --help`, `,ai-kb search --help`) rather than memory;
flags and enums are the source of truth. This file records the verified contract; the binary wins on conflict.
