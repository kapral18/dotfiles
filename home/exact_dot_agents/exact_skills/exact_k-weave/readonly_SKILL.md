---
name: k-weave
description: "Use when preparing/previewing merges, resolving semantic Git conflicts, setting up weave, or parsing markers."
---

# weave

Entity-level merge driver for Git. Replaces git's line-based merge with function/class-level merge via tree-sitter.
Two branches adding different functions to the same file can auto-resolve; input guards can still reject the merge.

Do not use:

- for diffing or analyzing changes (use the `k-sem` skill, which runs the `,sem` CLI)
- for non-code files that tree-sitter doesn't parse

First actions:

1. `command -v ,weave-setup-local` — abort if missing (this repo installs it to `~/bin/`).
2. `command -v weave-driver` — abort with install instructions (`brew install weave`) if missing.
3. Verify you're in a git repo: `git rev-parse --is-inside-work-tree`

## Commands

```bash
,weave-setup-local                          # configure current repo without creating `.gitattributes`
,weave-unsetup-local                        # revert local-only weave config for current repo
weave preview <branch>                      # dry-run: what would a merge look like?
weave preview <branch> --file <path>        # preview a specific file only
weave summary <path>                        # parse weave conflict markers, structured summary
weave summary <path> --json
```

After `,weave-setup-local`, use `git merge` as normal — weave acts as the merge driver transparently.

## How it works

1. Parses base, ours, theirs into entities (functions, classes, methods) via tree-sitter
2. Matches entities across versions by identity (name + type + scope)
3. Different entities changed → attempts auto-resolution, subject to input and merge guards
4. Same entity changed by both → attempts intra-entity merge; unresolved or guard-rejected cases conflict
5. Falls back to line-level merge for files >1MB or unsupported text types; `weave-driver` rejects binary input

## Conflict markers

When a real conflict occurs, weave provides entity context that git doesn't:

```text
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

TypeScript, TSX, JavaScript, Python, Go, Rust, Java, C, C++, Ruby, C#, PHP, Swift, Kotlin, Elixir, Bash, HCL/Terraform, Fortran, XML, JSON, YAML, TOML, CSV, Markdown.

Setup omits dedicated patterns for `.vue`, `.svelte`, `.erb`, and `.hs`.
Compound names such as `.svelte.ts` can still match `*.ts`; preview and direct-driver calls can also attempt entity merging.

## Notes

- `,weave-setup-local` configures weave via `.git/info/attributes` + repo-local git config, so nothing is added to repo history.
- Use `,weave-setup-local` instead of `weave setup` for day-to-day use: `weave setup` writes a repo-root `.gitattributes` (tracked by default) and tends to show up in PR diffs.
- Upstream reports wins and regressions across real-world benchmarks (git/git, CPython, Go, TypeScript, Flask);
  see its [versioned results](https://github.com/Ataraxy-Labs/weave/blob/v0.5.4/README.md#real-world-benchmarks).
- Conflict markers include the entity name and conflict reason for faster manual resolution.
