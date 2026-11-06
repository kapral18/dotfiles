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
- Ensure minimum sufficient test protection under `~/AGENTS.md` §3.
  Map each justified test to its production paths in `scripts/check.py`: `scripts/foo.py` → `scripts/tests/test_foo.py`, `home/exact_lib/exact_,name/` → `scripts/tests/test_name.py`, or a `TEST_RULES` row.

## Documentation and contributor conventions

- Read `CONTRIBUTING.md` before changing package installs, comma commands, or shell helpers.
- Keep repository-level documentation limited to setup/safety/recovery in `README.md` and editing/checks in `CONTRIBUTING.md`.
  Update them only when their instructions become incorrect, not for routine code changes.
- Do not add a docs website, command catalogs, configuration inventories, or checks requiring docs coverage.
  Command usage belongs in `--help` and shell completions.

## Skills

Repo-owned skills live in `home/exact_dot_agents/exact_skills/exact_k-<name>/readonly_SKILL.md`, deploy to `~/.agents/skills/k-<name>/SKILL.md`, and use the `k-` prefix in their frontmatter `name`.

## Global instructions

`home/readonly_AGENTS.md` is the global agent instruction file.
It deploys to `~/AGENTS.md`; Claude reads it through the `~/.claude/CLAUDE.md` and `~/CLAUDE.md` symlinks;
Pi, OMP, and Codex read it through `symlink_AGENTS.md` entries in their config dirs.
Keep it short: every byte loads into every session.
