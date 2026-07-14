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

`make check` runs formatting lint (`bin/fmt --check`), Python import lint, template rendering (`scripts/verify_templates.py`), mermaid file-census sync (`scripts/verify_mermaids.py`), bin command surface checks (`scripts/verify_bin_surface.py`), docs navigation checks (`scripts/verify_docs_navigation.py`), and the Python test suite.

Details on formatters: [`docs/topics/code-quality/formatting.md`](docs/topics/code-quality/formatting.md).

## Git hooks (optional)

This repo ships a local pre-commit hook at [`.githooks/pre-commit`](.githooks/pre-commit). Enable it **for this clone only**:

```bash
git config core.hooksPath .githooks
```

On commit, the hook first runs `bin/fmt --check` only on staged paths. If those staged files need repair, it runs `bin/fmt` on just those paths, re-stages them, and then runs the full `make check`. It refuses to auto-format when a staged file still has unstaged edits (to avoid breaking partial staging).

## Documentation

If a change under `home/`, `scripts/`, or `tools/` affects behavior, commands, or workflows, update the matching page under [`docs/`](docs/). If a change alters flows shown in [`.mermaids/`](.mermaids/), update the affected diagram in the same change.

Architecture map read order: [`.mermaids/README.md`](.mermaids/README.md).
