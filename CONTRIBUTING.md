# Contributing

This file is for people **editing this git repository** — not for day-to-day use of the deployed dotfiles. If you are bootstrapping a machine or changing your own setup, start with [`README.md`](README.md) and [`docs/intro/index.md`](docs/intro/index.md).

## Source of truth

- Chezmoi source lives under [`home/`](home/). Edit there, then `chezmoi apply` — do not edit deployed files under `$HOME` directly unless you know they are not managed.
- Agent workflow rules: [`AGENTS.md`](AGENTS.md)
- Where to change what: [`docs/reference/reference-map.md`](docs/reference/reference-map.md)

## Validation

Before opening a PR (or after any substantive change), run:

```bash
make fmt
make check
```

`make check` runs [`bin/check`](bin/check): affected formatting lint, Python import lint, verify gates, and tests for paths dirty vs `HEAD` (plus untracked). Affected tests are the union of filename convention (`scripts/foo.sh` → `test_foo.py`), one-hop Python imports among `scripts/*.py`, and the prefix map in [`scripts/check.py`](scripts/check.py). Slow picker shards run only when tmux sources (or those shards) change. Humans may run the full suite with `make check-full` (`CHECK_FULL=1 bin/check --full`). Agents must not. Pre-commit never runs the full suite. `make test` is also human-only.

Affected Python tests run in parallel via [`scripts/test_runner.py`](scripts/test_runner.py), usually one subprocess per selected file; the runner splits a few slow files into individual cases. Each shard gets disposable working, home, XDG, temporary, and tmux socket directories. Only `PATH`, locale variables, `TERM`, and the explicit integration-test opt-in pass through from the shell—not credentials, Git selectors, or tmux state. `scripts/test_runner.py` itself is not a shard.

### Test quality and isolation

- Keep tests that catch a consumer-visible regression: wrong results, lost data, unsafe side effects, broken transitions, or errors. Fewer useful cases beat more assertions.
- Do not pin prose, source snippets, helper names, or mock responses against themselves. Exercise the real implementation and assert returned values or resulting state. Validate declarative configuration against its consumer's contract, not incidental spelling.
- Create fixtures outside the checkout with `TemporaryDirectory` or the runtime's equivalent. Treat source files as read-only; copy them into a disposable repository before testing writers, generators, formatting, hooks, or deletion.
- Give subprocesses temporary `HOME` and XDG paths. Clear inherited Git repository selectors. Use a private tmux socket and stop it in cleanup; never address the user's default server.
- Stub external side effects at the boundary. Default checks must not deploy dotfiles, install software, contact live services, or mutate the user's files.
- Register cleanup as soon as resources are created, including failed setup and failed assertions. Avoid fixed temporary names, sleeps as synchronization, and shared mutable fixtures.

The Python runner's environment isolation is not a security sandbox. Tests can still reach explicit paths and executables. Direct unittest runs and non-Python suites must provide their own isolation.

The AI-KB model/vector integrations are separate from default checks. To run them explicitly:

```bash
AI_KB_LIVE_TESTS=1 python3 scripts/test_runner.py test_ai_kb.py
```

This opt-in may download Python dependencies and model weights into disposable caches. Normal checks skip those integrations; storage, lexical ranking, duplicate refusal, and CLI tests run offline.

Details on formatters: [`docs/topics/code-quality/formatting.md`](docs/topics/code-quality/formatting.md).

## Git hooks (optional)

This repo ships a local pre-commit hook at [`.githooks/pre-commit`](.githooks/pre-commit). Enable it **for this clone only**:

```bash
git config core.hooksPath .githooks
```

On commit, the hook first runs `bin/fmt --check` only on staged paths. If those staged files need repair, it runs `bin/fmt` on just those paths, re-stages them, and then runs `bin/check --staged` (affected gates and tests for the index). It never runs `bin/check --full`. It refuses to auto-format when a staged file still has unstaged edits (to avoid breaking partial staging).

## Documentation

If a change under `home/`, `scripts/`, or `tools/` affects behavior, commands, or workflows, update the matching page under [`docs/`](docs/).
