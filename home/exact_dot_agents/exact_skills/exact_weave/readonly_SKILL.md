---
name: weave
description: Entity-level semantic merge driver for Git via weave CLI. Use when preparing merges, previewing merge conflicts, or resolving merge conflicts at function/class granularity.
---

# weave

Entity-level merge driver for Git. Replaces git's line-based merge with function/class-level merge via tree-sitter. Two branches adding different functions to the same file? Auto-resolved, zero conflicts. Only truly incompatible changes to the *same entity* produce conflicts.

Use when:

- preparing or previewing a merge and want to see what weave would resolve vs conflict
- setting up a repo to use entity-level merging
- resolving merge conflicts (weave handles most false conflicts automatically)
- parsing weave conflict markers after a merge

Do not use:

- for diffing or analyzing changes (use the `sem` skill)
- for non-code files that tree-sitter doesn't parse

First actions:

1. `command -v weave-setup-local` — abort if missing (this repo installs it to `~/bin/`).
2. `command -v weave-driver` — abort with install instructions (`brew install weave`) if missing.
3. Verify you're in a git repo: `git rev-parse --is-inside-work-tree`

## Commands

```bash
weave-setup-local                           # configure current repo without creating `.gitattributes`
weave-unsetup-local                         # revert local-only weave config for current repo
weave preview <branch>                      # dry-run: what would a merge look like?
weave preview <branch> --file <path>        # preview a specific file only
weave summary <path>                        # parse weave conflict markers, structured summary
weave summary <path> --json
```

After `weave-setup-local`, use `git merge` as normal — weave acts as the merge driver transparently.

## How it works

1. Parses base, ours, theirs into entities (functions, classes, methods) via tree-sitter
2. Matches entities across versions by identity (name + type + scope)
3. Different entities changed → auto-resolved, no conflict
4. Same entity changed by both → attempts intra-entity merge, conflicts only if truly incompatible
5. Falls back to line-level merge for files >1MB, binary files, or unsupported types

## Conflict markers

When a real conflict occurs, weave provides entity context that git doesn't:

```
<<<<<<< ours — function `process` (both modified)
export function process(data: any) {
    return JSON.stringify(data);
}
=======
export function process(data: any) {
    return data.toUpperCase();
}
>>>>>>> theirs — function `process` (both modified)
```

## Supported languages

TypeScript, TSX, JavaScript, Python, Go, Rust, Java, C, C++, Ruby, C#, PHP, Swift, Kotlin, Elixir, Bash, HCL/Terraform, Fortran, Vue, XML, ERB, JSON, YAML, TOML, CSV, Markdown.

## Notes

- `weave-setup-local` configures weave via `.git/info/attributes` + repo-local git config, so nothing is added to repo history.
- Avoid `weave setup` for day-to-day use: it writes a repo-root `.gitattributes` (tracked by default) and tends to show up in PR diffs.
- Zero regressions across real-world benchmarks (git/git, CPython, Go, TypeScript, Flask).
- Conflict markers include the entity name and conflict reason for faster manual resolution.
