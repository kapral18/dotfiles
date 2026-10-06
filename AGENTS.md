# Dotfiles Repo — Agent Instructions

## Chezmoi source of truth

This repo is chezmoi source. Files under `home/` deploy to `$HOME`; deployed copies are outputs that `chezmoi apply` overwrites.

Before editing any file under `$HOME`:

1. Resolve symlinks (`realpath <path>`); `chezmoi source-path` does not follow them.
2. Run `chezmoi source-path <resolved-path>`.
3. Managed: edit only the source under `home/`, then `chezmoi apply --no-tty <target>`.
4. Not managed and writable: edit it directly.
5. Not managed but read-only (`r--r--r--`): stop and search `home/` for the filename. Never `chmod` a deployed file.

Name prefixes: `exact_` exact directory (apply deletes untracked files), `readonly_`, `executable_`, `private_`, `dot_` (leading `.`), `.tmpl` template.

## Validation

- Run `make fmt` after editing, and `make check` once on the finished change. `make check` covers only affected paths.
- Never run `make check-full`, `bin/check --full`, or `make test`; those are for the human.
- New code needs a test that `scripts/check.py` maps to it: `scripts/foo.py` → `scripts/tests/test_foo.py`, `home/exact_lib/exact_,name/` → `scripts/tests/test_name.py`, or add a `TEST_RULES` row.

## Docs

- A change to behavior, commands, or install logic under `home/` updates the matching page in `docs/` in the same change.
- Before adding or changing package installs, comma commands, or shell helper structure, read `docs/topics/workflow/dotfiles-recipes.md`.

## Skills

Repo-owned skills live in `home/exact_dot_agents/exact_skills/exact_k-<name>/readonly_SKILL.md`, deploy to `~/.agents/skills/k-<name>/SKILL.md`, and use the `k-` prefix in their frontmatter `name`.

## Global instructions

`home/readonly_AGENTS.md` is the global agent instruction file.
It deploys to `~/AGENTS.md`; Claude reads it through `~/.claude/CLAUDE.md` (symlink) and `~/CLAUDE.md` (`@AGENTS.md` import);
Pi, OMP, Codex, OpenCode, and Antigravity read it through `symlink_AGENTS.md` entries in their config dirs.
Keep it short: every byte loads into every session.
