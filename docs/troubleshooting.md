# Troubleshooting

Back: [`docs/index.md`](index.md)

This setup wires a lot of automation into `chezmoi apply`. When something goes
wrong, start by identifying whether you're dealing with:

1. A template rendering problem
2. A hook script failing
3. A missing dependency (brew/asdf/op/gh/etc.)

## First Checks

```bash
chezmoi diff
chezmoi apply
```

If `chezmoi apply` errors, the failing script path is usually the most useful
signal.

## 1Password Readiness Gate

`home/.chezmoi.toml.tmpl` exits early if you answer "no" to "Is 1Password ready".
Make sure the 1Password app is installed, unlocked, and the SSH agent is
available.

Relevant files:

- `home/.chezmoi.toml.tmpl`
- `home/private_dot_ssh/private_executable_config`

## Brew Bundle Cleanup Surprise

The brew hook runs cleanup in addition to install:

- `home/.chezmoiscripts/run_onchange_after_03-install-brew-packages.fish.tmpl`

If you had packages installed manually (outside the Brewfile), they can be
removed. Treat the Brewfile as the source-of-truth.

## GitHub CLI Auth Prompts

The GitHub extensions hook will run `gh auth login` if you're not authenticated:

- `home/.chezmoiscripts/run_onchange_after_05-install-gh-extensions.fish.tmpl`

The manual packages installer also relies on `gh release download`:

- `home/.chezmoiscripts/run_onchange_after_05-install-manual-packages.sh.tmpl`

## Password Store Setup

If you see missing API keys or tools failing to authenticate, check whether
`pass` is set up and your password store repo is present.

- Setup script: `home/.chezmoiscripts/run_once_after_05-setup-pass-managers.fish.tmpl`
- Shell wiring: `home/dot_config/fish/config.fish.tmpl`

## See Also

- Debug a failing hook: [`docs/recipes/debugging-chezmoi-hooks.md`](recipes/debugging-chezmoi-hooks.md)
