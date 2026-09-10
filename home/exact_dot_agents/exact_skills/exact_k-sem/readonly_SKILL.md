---
name: k-sem
description: "Use when entity history across file moves, per-entity blame, or entity-level diff with rename/cosmetic classification needs ,sem; indexed structural queries only on explicit request."
---

# ,sem

Entity-level Git CLI (Ataraxy `sem-cli` from homebrew-core, launched through `~/bin/,sem`).
Shows what _entities_ changed (functions, classes, methods) instead of what lines changed.

## Scope

Index-free, use freely: `diff`, `log`, `blame`. They parse only the files git hands them and write nothing (Kibana 8.19: 0.1-2.5 s cold).
Indexed, restricted: `impact`, `context`, `find`, `callers`, `refs`, `grep`, `entities`, `graph`.
They build a per-worktree query index plus entity graph (Kibana 8.19: about 2m20s plus 2m45s and several GB under `~/.cache/sem`), they do not resolve bare package specifiers such as `@kbn/*` (cross-package results miss real consumers and add false ones), and `impact` stops at `--depth 2` by default.
NEVER run an indexed subcommand unless the user explicitly asks for it; for impact and base context use `~/.agents/skills/k-semantic-code-search/SKILL.md` (SCSI, then `rg`).
When the user does ask: stay inside one package, pass `--depth 0` across barrel chains, disambiguate with `--file`, and confirm every result with `rg`.

Do not use:

- for merging branches (use the `k-weave` skill)
- for line-level diffs where entity granularity adds no value
- `"$SEM_BIN" setup` / `"$SEM_BIN" unsetup`: upstream setup writes a `sem-diff-wrapper` that execs bare `sem`, which is intentionally not on PATH in this dotfiles setup.
- `mcp` / `hook`: the CLI already returns JSON and our hooks own prompt-time context.
- NEVER run `telemetry on`, `cloud enable`/`cloud share`, `login`, or `update`:
  the `~/bin/,sem` launcher exports `DO_NOT_TRACK=1 SEM_NO_TELEMETRY=1 SEM_NO_UPDATE_CHECK=1 SEM_NO_NETWORK=1`, chezmoi owns `~/.sem/telemetry.json` (mode `off`), and Homebrew owns upgrades.

First actions:

1. Resolve the binary explicitly through the chezmoi-managed wrapper; do not trust PATH order:
   - `SEM_BIN="$HOME/bin/,sem"; [ -x "$SEM_BIN" ] || { echo "missing ~/bin/,sem; run chezmoi apply --no-tty ~/bin/,sem"; exit 1; }`
   - if `"$SEM_BIN" --version` reports a missing Homebrew formula, install it with `brew install sem-cli`.
   - Never fall back to bare `sem`; GNU parallel can also provide that command name.
2. Verify identity before relying on behavior: `"$SEM_BIN" --version` (or `--help`).
3. Verify you're in a git repo: `git rev-parse --is-inside-work-tree`

## Commands (index-free)

```bash
"$SEM_BIN" diff                              # entity-level diff of tracked working changes (untracked files are excluded)
"$SEM_BIN" diff --staged                     # staged changes only
"$SEM_BIN" diff --commit abc1234             # one commit
"$SEM_BIN" diff --from HEAD~5 --to HEAD      # commit range (also: diff ref1..ref2, diff -- <paths>)
"$SEM_BIN" diff -v                           # inline word-level diffs per entity
"$SEM_BIN" diff --format json|markdown       # machine-readable / PR-ready output
"$SEM_BIN" diff --file-exts .ts .tsx         # limit file types
"$SEM_BIN" diff --stdin --format json        # FileChange[] JSON from stdin, no git repo needed

"$SEM_BIN" log <entity> --file <path>        # entity evolution across commits, moves, and renames
"$SEM_BIN" log <entity> --file <path> -v     # with content diffs between versions
"$SEM_BIN" log <entity> --limit 20 --json
"$SEM_BIN" log --limit 50                    # no entity: repo hotspots + co-change pairs

"$SEM_BIN" blame <path>                      # who last changed each entity in the file
"$SEM_BIN" blame <path> --json
```

## Mechanical-only proof (SOP §2.1)

Run `"$SEM_BIN" diff --format json` on the exact change set (working tree, `--staged`, or `--from`/`--to`).
The change is mechanical-only when every entry in `changes` is `renamed`/`moved` or has `structuralChange: false`, and `summary.total` matches the entries you accounted for.
Untracked files are excluded from `diff`; account for them separately.
Any `modified` entity with `structuralChange: true` is a semantic change: reconstruct the semantic delta.

## Entity history (review archaeology)

`log <entity> --file <path>` follows one entity across file moves and renames where `git log -L` stops;
rows carry commit, author, date, and `added`/`moved`/`modified`. `blame <path>` attributes each entity's last change.
Use `--json`, keep raw output in a task artifact, and cite commit plus file in findings.

## Supported languages

TypeScript, TSX, JavaScript, Python, Go, Rust, Java, C, C++, Ruby, C#, PHP, Swift, Kotlin, Elixir, Bash, HCL/Terraform, Fortran, Vue, XML, ERB, Svelte.

Structured data: JSON, YAML, TOML, CSV, Markdown.

Falls back to chunk-based diffing for unsupported file types.

## Notes

- Detects renames and moves via structural hashing (same AST structure, different name).
- `diff --format json` buckets every change as `added`, `modified`, `deleted`, `moved`, `renamed`, or `reordered`, each with a `structuralChange` flag.
- `--json` / `--format json` on any command produces machine-readable output.
