# Contributing

This file is for people **editing this git repository** — not for day-to-day use of the deployed dotfiles. If you are bootstrapping a machine or changing your own setup, start with [`README.md`](README.md) and [`docs/intro/index.md`](docs/intro/index.md).

## Source of truth

- Chezmoi source lives under [`home/`](home/). Edit there, then `chezmoi apply` — do not edit deployed files under `$HOME` directly unless you know they are not managed.
- Agent workflow rules: [`AGENTS.md`](AGENTS.md)
- Where to change what: [`docs/reference/reference-map.md`](docs/reference/reference-map.md)

## Validation

Before opening a PR (or after any substantive change), run:

```bash
make check
make fmt
```

`make check` runs [`bin/check`](bin/check): affected formatting lint, Python import lint, verify gates, and tests for paths dirty vs `HEAD` (plus untracked). Affected tests are the union of filename convention (`scripts/foo.sh` → `test_foo.py`), one-hop Python imports among `scripts/*.py`, and the prefix map in [`scripts/check.py`](scripts/check.py). Slow picker shards run only when tmux sources (or those shards) change. Humans may run the full suite with `make check-full` (`CHECK_FULL=1 bin/check --full`). Agents must not. Pre-commit never runs the full suite. `make test` is also human-only.

Affected Python tests run file-sharded in parallel via [`scripts/test_runner.py`](scripts/test_runner.py) (one subprocess per selected `test_*.py` file, per-file `AGENT_MEMORY_SPEC_ROOT` isolation). `scripts/test_runner.py` itself is not a shard. Tests that snapshot the working tree (`test_verify_mermaids.py`) run in a lead phase so they cannot race shard `__pycache__` churn.

Details on formatters: [`docs/topics/code-quality/formatting.md`](docs/topics/code-quality/formatting.md).

## Git hooks (optional)

This repo ships a local pre-commit hook at [`.githooks/pre-commit`](.githooks/pre-commit). Enable it **for this clone only**:

```bash
git config core.hooksPath .githooks
```

On commit, the hook first runs `bin/fmt --check` only on staged paths. If those staged files need repair, it runs `bin/fmt` on just those paths, re-stages them, and then runs `bin/check --staged` (affected gates and tests for the index). It never runs `bin/check --full`. It refuses to auto-format when a staged file still has unstaged edits (to avoid breaking partial staging).

## Documentation

If a change under `home/`, `scripts/`, or `tools/` affects behavior, commands, or workflows, update the matching page under [`docs/`](docs/). If a change alters flows shown in [`.mermaids/`](.mermaids/), update the affected diagram in the same change.

Architecture map read order: [`.mermaids/README.md`](.mermaids/README.md).
