---
name: sem
description: Use sem for entity-level Git diff, blame, impact analysis, and token-budgeted LLM context.
---

# sem

Entity-level Git CLI. Shows what _entities_ changed (functions, classes, methods, structs) instead of what lines changed.

Use when:

- reviewing changes and you want entity-level granularity (what functions were added/modified/deleted)
- investigating blast radius or dependency impact before or after a change
- generating token-budgeted context for an LLM about a specific entity
- tracing the history of a specific function or class through git log
- getting entity-level blame

Do not use:

- for merging branches (use the `weave` skill)
- for line-level diffs where entity granularity adds no value

First actions:

1. Resolve the binary explicitly — prefer the chezmoi-managed wrapper, do not trust PATH order:
   - `SEM_BIN="$HOME/bin/,sem"; [ -x "$SEM_BIN" ] || SEM_BIN="$(command -v sem)"`
   - abort with install instructions (`brew install ataraxy-labs/tap/sem`) if neither resolves.
   - The `~/bin/,sem` wrapper forwards to the Homebrew binary, so both are functionally identical;
     use `"$SEM_BIN"` consistently to avoid the "which sem?" ambiguity.
2. Verify identity before relying on behavior: `"$SEM_BIN" --version` (or `--help`).
3. Verify you're in a git repo: `git rev-parse --is-inside-work-tree`

## Commands

```bash
"$SEM_BIN" diff                             # entity-level diff of working changes
"$SEM_BIN" diff --staged                    # staged changes only
"$SEM_BIN" diff --commit abc1234            # specific commit
"$SEM_BIN" diff --from HEAD~5 --to HEAD     # commit range
"$SEM_BIN" diff -v                          # verbose: word-level inline diffs per entity
"$SEM_BIN" diff --format json               # JSON output (for piping/parsing)
"$SEM_BIN" diff --format markdown           # markdown output
"$SEM_BIN" diff --format plain              # git-status style
"$SEM_BIN" diff --file-exts .py .rs         # limit to specific file types
"$SEM_BIN" diff file1.ts file2.ts           # compare two files (no git needed)

"$SEM_BIN" impact <entity> --file <path>    # full impact analysis (deps + dependents + tests)
"$SEM_BIN" impact <entity> --deps           # direct dependencies only
"$SEM_BIN" impact <entity> --dependents     # direct dependents only
"$SEM_BIN" impact <entity> --tests          # affected tests only
"$SEM_BIN" impact <entity> --json           # JSON output

"$SEM_BIN" blame <path>                     # entity-level blame
"$SEM_BIN" blame <path> --json

"$SEM_BIN" log <entity>                     # history of one entity through git log
"$SEM_BIN" log <entity> -v                  # with content diffs between versions
"$SEM_BIN" log <entity> --limit 20

"$SEM_BIN" entities <path>                  # list all entities in a file
"$SEM_BIN" entities <path> --json

"$SEM_BIN" context <entity> --file <path>   # token-budgeted context: entity + deps + dependents
"$SEM_BIN" context <entity> --budget 4000   # custom token budget (default 8000)
"$SEM_BIN" context <entity> --json
```

## Supported languages

TypeScript, TSX, JavaScript, Python, Go, Rust, Java, C, C++, Ruby, C#, PHP, Swift, Kotlin, Elixir, Bash, HCL/Terraform, Fortran,
Vue, XML, ERB, Svelte.

Structured data: JSON, YAML, TOML, CSV, Markdown.

Falls back to chunk-based diffing for unsupported file types.

## Notes

- Detects renames and moves via structural hashing (same AST structure, different name).
- `"$SEM_BIN" context` fits the entity, its dependencies, and its dependents into a token budget — useful for feeding targeted context to an LLM.
- `--format json` on any command produces machine-readable output.
- `"$SEM_BIN" setup` replaces `git diff` globally so everything that calls `git diff` gets entity-level output. `"$SEM_BIN" unsetup` reverts.
