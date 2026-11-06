# Contributing

## Edit the source

Chezmoi deploys [`home/`](home/) into `$HOME`. Resolve symlinks and run `chezmoi source-path <target>` before editing a deployed file; edit its source, then apply that target. `exact_` directories delete unmanaged entries; `readonly_` outputs must be changed at their source.

- **Packages:** prefer Homebrew, then Cargo, Go, Gems, pnpm, uv, then custom release installers. Honor an existing `@install-priority-exception` directive unless the user requests changing it. Verify the upstream project and package identity before choosing a manager. Homebrew entries belong in `home/.chezmoitemplates/brews/`; when creating a category partial, add its `includeTemplate` entry to `home/.chezmoitemplates/brews/_assemble.brewfile`. Other registries are `home/readonly_dot_default-*`.
- **Shell hooks:** keep shell as glue. Put parsing and non-trivial logic in standard-library helpers under `scripts/`.
- **Commands:** use `home/exact_bin/executable_,<name>` and keep the matching Fish completion in `home/dot_config/fish/completions/readonly_,<name>.fish` and any existing zsh completion in `home/dot_zsh/completions/` in sync. Large commands use a thin launcher with internals in `home/exact_lib/exact_,<name>/`. Deployed commands cannot depend on repo-only `scripts/` helpers.

## Validate

```sh
make fmt
make check
```

`make check` runs affected formatting, import lint, verification gates, and isolated tests for changes against `HEAD`, including untracked files. Test selection uses filename conventions, one-hop Python imports, and `TEST_RULES` in [`scripts/check.py`](scripts/check.py).

Keep only tests that protect meaningful behavior: results, data safety, side effects, or state transitions. Do not pin prose or private implementation structure. Use disposable fixtures outside the checkout, temporary HOME/XDG paths, and fakes for external side effects. Never let default checks deploy dotfiles, install packages, contact live services, or mutate user files. The Python test runner isolates shard environments; this is not a security sandbox, and direct test runs need their own isolation.

The local hook at [`.githooks/pre-commit`](.githooks/pre-commit) formats staged paths and runs affected checks when configured with `git config core.hooksPath .githooks`. It refuses automatic formatting of partially staged files.
