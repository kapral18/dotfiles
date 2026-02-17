# Chezmoi

Back: [`docs/categories/index.md`](index.md)

This setup uses `chezmoi` to keep a macOS development environment reproducible.

If you have not used `chezmoi` before, start at
[`docs/getting-started.md`](../getting-started.md).

## Source Layout

- `home/` contains files that will be written into `$HOME`.
- Templates use `*.tmpl` and access `chezmoi` data (like `.isWork`).
- Hooks live in `home/.chezmoiscripts/`.
- Externals live in `home/.chezmoiexternal.toml`.

If you are reading the source on GitHub, you can treat `home/` as "what gets
installed".

## Render Model

Prompt definitions and computed values are defined in:

- `home/.chezmoi.toml.tmpl`

This is where machine-specific values are decided (for example `isWork`,
emails, `homebrewPrefix`, and cache TTL values).

If something renders differently than expected, start by inspecting this file.

## Hook Pipeline (High Signal)

The first-run and converge flow is driven by ordered scripts in
`home/.chezmoiscripts/`:

- `run_once_before_00-install-xcode.sh`
- `run_once_after_01-install-brew.sh`
- `run_once_after_02-install-fish.sh`
- `run_onchange_after_03-install-brew-packages.fish.tmpl`
- `run_onchange_after_04-update-fish-packages.fish.tmpl`
- `run_onchange_after_05-*` package, OS, and integration scripts
- `run_onchange_after_06-update-uv-tools.sh.tmpl`

This is the first place to look when `chezmoi apply` fails.

## Core Workflows

### Safe apply loop

```bash
chezmoi diff
chezmoi apply
```

Use `chezmoi diff` before apply whenever you changed templates or prompt data.

### Pull remote changes safely

```bash
chezmoi update --apply=false
chezmoi diff
chezmoi apply
```

### Debug a failing hook

1. Re-run and capture the failing script path:

```bash
chezmoi apply
```

2. If it is a template hook, render it directly:

```bash
chezmoi execute-template < home/.chezmoiscripts/<script>.tmpl
```

3. Run the generated command or script directly to isolate dependency issues.

## Verification And Troubleshooting

Useful checks:

```bash
chezmoi doctor
chezmoi status
chezmoi diff
```

Externals can be refreshed with:

```bash
chezmoi apply -R always
```

If a script fails with `command not found`, check whether its prerequisite hook
(usually Homebrew/ASDF) ran successfully.

## Related

- New machine bootstrap: [`docs/recipes/new-machine-bootstrap.md`](../recipes/new-machine-bootstrap.md)
- Debugging hooks: [`docs/recipes/debugging-chezmoi-hooks.md`](../recipes/debugging-chezmoi-hooks.md)
- Refreshing externals: [`docs/recipes/refreshing-externals.md`](../recipes/refreshing-externals.md)
- Updating: [`docs/recipes/updating.md`](../recipes/updating.md)
