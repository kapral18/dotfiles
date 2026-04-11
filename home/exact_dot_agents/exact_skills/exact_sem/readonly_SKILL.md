---
name: sem
description: Entity-level diff, blame, impact analysis, and LLM context for Git via sem CLI. Use when diffing changes at function/class granularity, investigating blast radius, tracing entity history, or generating token-budgeted code context.
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

1. `command -v sem` — abort with install instructions (`brew install ataraxy-labs/tap/sem`) if missing.
2. Verify you're in a git repo: `git rev-parse --is-inside-work-tree`

## Commands

```bash
sem diff                                    # entity-level diff of working changes
sem diff --staged                           # staged changes only
sem diff --commit abc1234                   # specific commit
sem diff --from HEAD~5 --to HEAD            # commit range
sem diff -v                                 # verbose: word-level inline diffs per entity
sem diff --format json                      # JSON output (for piping/parsing)
sem diff --format markdown                  # markdown output
sem diff --format plain                     # git-status style
sem diff --file-exts .py .rs                # limit to specific file types
sem diff file1.ts file2.ts                  # compare two files (no git needed)

sem impact <entity> --file <path>           # full impact analysis (deps + dependents + tests)
sem impact <entity> --deps                  # direct dependencies only
sem impact <entity> --dependents            # direct dependents only
sem impact <entity> --tests                 # affected tests only
sem impact <entity> --json                  # JSON output

sem blame <path>                            # entity-level blame
sem blame <path> --json

sem log <entity>                            # history of one entity through git log
sem log <entity> -v                         # with content diffs between versions
sem log <entity> --limit 20

sem entities <path>                         # list all entities in a file
sem entities <path> --json

sem context <entity> --file <path>          # token-budgeted context: entity + deps + dependents
sem context <entity> --budget 4000          # custom token budget (default 8000)
sem context <entity> --json
```

## Supported languages

TypeScript, TSX, JavaScript, Python, Go, Rust, Java, C, C++, Ruby, C#, PHP, Swift, Kotlin, Elixir, Bash, HCL/Terraform, Fortran, Vue, XML, ERB, Svelte.

Structured data: JSON, YAML, TOML, CSV, Markdown.

Falls back to chunk-based diffing for unsupported file types.

## Notes

- Detects renames and moves via structural hashing (same AST structure, different name).
- `sem context` fits the entity, its dependencies, and its dependents into a token budget — useful for feeding targeted context to an LLM.
- `--format json` on any command produces machine-readable output.
- `sem setup` replaces `git diff` globally so everything that calls `git diff` gets entity-level output. `sem unsetup` reverts.
