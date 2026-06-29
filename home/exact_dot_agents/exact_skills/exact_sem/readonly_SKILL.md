---
name: sem
description: Use ,sem for entity-level Git diff, blame, impact analysis, and dependency graphs.
---

# ,sem

Entity-level Git CLI. Shows what _entities_ changed (functions, classes, methods, structs) instead of what lines changed.

Use when:

- reviewing changes and you want entity-level granularity (what functions were added/modified/deleted)
- investigating blast radius or dependency impact before or after a change
- inspecting entity dependency graphs
- tracing the history of a specific function or class through git log
- getting entity-level blame

Do not use:

- for merging branches (use the `weave` skill)
- for line-level diffs where entity granularity adds no value
- `"$SEM_BIN" setup` / `"$SEM_BIN" unsetup`: upstream setup writes a `sem-diff-wrapper` that execs bare `sem`, which is intentionally not on PATH in this dotfiles setup.

First actions:

1. Resolve the binary explicitly through the chezmoi-managed wrapper; do not trust PATH order:
   - `SEM_BIN="$HOME/bin/,sem"; [ -x "$SEM_BIN" ] || { echo "missing ~/bin/,sem; run chezmoi apply --no-tty ~/bin/,sem"; exit 1; }`
   - if `"$SEM_BIN" --version` reports a missing Homebrew formula, install it with `brew install ataraxy-labs/tap/sem`.
   - Never fall back to bare `sem`; GNU parallel can also provide that command name.
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
"$SEM_BIN" diff --format terminal           # terminal output
"$SEM_BIN" diff --file-exts .py .rs         # limit to specific file types
"$SEM_BIN" diff file1.ts file2.ts           # compare two files (no git needed)

"$SEM_BIN" impact <entity>                  # impact analysis for an entity
"$SEM_BIN" impact <entity> --files <paths>  # analyze specific files
"$SEM_BIN" impact <entity> --file-exts .py  # limit to specific file types
"$SEM_BIN" impact <entity> --json           # JSON output

"$SEM_BIN" blame <path>                     # entity-level blame
"$SEM_BIN" blame <path> --json

"$SEM_BIN" graph                            # entity dependency graph
"$SEM_BIN" graph --entity <entity>          # dependencies/dependents for one entity
"$SEM_BIN" graph --format json              # JSON output

"$SEM_BIN" log <entity>                     # history of one entity through git log
"$SEM_BIN" log <entity> --file <path>       # disambiguate entity location
"$SEM_BIN" log <entity> -v                  # with content diffs between versions
"$SEM_BIN" log <entity> --limit 20
"$SEM_BIN" log <entity> --json              # JSON output
```

## Supported languages

TypeScript, TSX, JavaScript, Python, Go, Rust, Java, C, C++, Ruby, C#, PHP, Swift, Kotlin, Elixir, Bash, HCL/Terraform, Fortran,
Vue, XML, ERB, Svelte.

Structured data: JSON, YAML, TOML, CSV, Markdown.

Falls back to chunk-based diffing for unsupported file types.

## Notes

- Detects renames and moves via structural hashing (same AST structure, different name).
- `--format json` on any command produces machine-readable output.
