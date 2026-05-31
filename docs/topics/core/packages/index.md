# Packages

This setup treats package installation as declarative.

That means:

- you edit a list (Brewfile / cargo crates / go pkgs / gems / yarn / uv tools)
- you run `chezmoi apply`
- hooks install missing items and (in some systems) remove items no longer listed

The core workflow is:

1. Edit the list file in [`home/`](../../../../home/)
2. Run `chezmoi apply`
3. Verify the tool is installed / available

## Package sources at a glance

| Source                 | List file                                                                                                      | Hook                                                    | Scoped |
| ---------------------- | -------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------- | ------ |
| Homebrew               | [`home/readonly_dot_Brewfile.tmpl`](../../../../home/readonly_dot_Brewfile.tmpl)                               | `run_onchange_after_03-install-brew-packages.fish.tmpl` | Yes    |
| mise                   | [`home/dot_config/mise/config.toml.tmpl`](../../../../home/dot_config/mise/config.toml.tmpl)                   | `run_onchange_after_05-install-mise-runtimes.sh.tmpl`   | Yes    |
| Cargo                  | [`home/readonly_dot_default-cargo-crates`](../../../../home/readonly_dot_default-cargo-crates)                 | `run_onchange_after_05-update-cargo-crates.sh.tmpl`     | No     |
| Go                     | [`home/readonly_dot_default-golang-pkgs.tmpl`](../../../../home/readonly_dot_default-golang-pkgs.tmpl)         | `run_onchange_after_05-update-golang-pkgs.sh.tmpl`      | Yes    |
| Ruby gems              | [`home/readonly_dot_default-gems`](../../../../home/readonly_dot_default-gems)                                 | `run_onchange_after_05-update-gems.sh.tmpl`             | No     |
| yarn                   | [`home/readonly_dot_default-yarn-pkgs`](../../../../home/readonly_dot_default-yarn-pkgs)                       | `run_onchange_after_05-update-yarn-pkgs.sh.tmpl`        | No     |
| uv tools               | [`home/readonly_dot_default-uv-tools.tmpl`](../../../../home/readonly_dot_default-uv-tools.tmpl)               | `run_onchange_after_06-update-uv-tools.sh.tmpl`         | Yes    |
| gh extensions          | —                                                                                                              | `run_onchange_after_05-install-gh-extensions.fish.tmpl` | —      |
| Custom (GitHub/source) | [`home/readonly_dot_default-custom-packages.tmpl`](../../../../home/readonly_dot_default-custom-packages.tmpl) | `run_onchange_after_05-install-custom-packages.sh.tmpl` | Yes    |

"Scoped" means the list is a chezmoi template that can branch on `.isWork`. All hooks live under [`home/.chezmoiscripts/`](../../../../home/.chezmoiscripts/).

## Scope-aware package lists

Some package sources are plain lists and apply everywhere (`cargo`, `yarn`, `gems`). Others are templates and can branch on `chezmoi` data like `.isWork`.

Use template conditionals when a package should only exist on personal or work machines, for example:

```gotemplate
{{ if ne .isWork true -}}
brew "torf-cli"
{{ end -}}
```

In practice:

- [`home/readonly_dot_Brewfile.tmpl`](../../../../home/readonly_dot_Brewfile.tmpl) supports personal/work scoping.
- [`home/readonly_dot_default-uv-tools.tmpl`](../../../../home/readonly_dot_default-uv-tools.tmpl) supports personal/work scoping.
- [`home/readonly_dot_default-cargo-crates`](../../../../home/readonly_dot_default-cargo-crates) and [`home/readonly_dot_default-yarn-pkgs`](../../../../home/readonly_dot_default-yarn-pkgs) are shared lists.

## Homebrew (Brewfile)

- Source: [`home/readonly_dot_Brewfile.tmpl`](../../../../home/readonly_dot_Brewfile.tmpl)
- Installed as: `~/.Brewfile`
- Hook: [`home/.chezmoiscripts/run_onchange_after_03-install-brew-packages.fish.tmpl`](../../../../home/.chezmoiscripts/run_onchange_after_03-install-brew-packages.fish.tmpl)

The hook runs:

- `brew bundle cleanup --global --force`
- `brew bundle --global`

So the Brewfile acts like the source-of-truth.

If you are new to this style: it is closer to "infrastructure as code" than "I installed a thing once".

The Brewfile also carries day-to-day terminal utilities, network diagnostics such as NetWatch, GUI apps, browser casks such as Helium, Brave, Zen, Arc, and Dia, and personal-only casks such as Roblox and Roblox Studio.

Some Homebrew formulae are deliberately installed with `link: false` when their binaries collide. For example, GNU `parallel` and Ataraxy semantic-git `sem` both provide a `sem` binary, so both formulae stay unlinked. The commands are exposed through managed wrappers at [`home/exact_bin/executable_parallel`](../../../../home/exact_bin/executable_parallel) and [`home/exact_bin/executable_sem`](../../../../home/exact_bin/executable_sem).

## mise (Tool Versions)

- Config source: [`home/dot_config/mise/config.toml.tmpl`](../../../../home/dot_config/mise/config.toml.tmpl)
- Installed as: `~/.config/mise/config.toml`
- Hook: [`home/.chezmoiscripts/run_onchange_after_05-install-mise-runtimes.sh.tmpl`](../../../../home/.chezmoiscripts/run_onchange_after_05-install-mise-runtimes.sh.tmpl)

That hook:

- runs `mise install --yes` to converge configured runtimes
- runs `mise reshim` to refresh shims after runtime/package updates
- respects project-level `.tool-versions` files when present
- enables `.nvmrc` support for Node via `idiomatic_version_file_enable_tools = ["node"]`

If you only adopt one idea from this setup, make it this: pin your tool versions so projects behave consistently across machines.

## Cargo crates

- List: [`home/readonly_dot_default-cargo-crates`](../../../../home/readonly_dot_default-cargo-crates)
- Installed as: `~/.default-cargo-crates`
- Hook: [`home/.chezmoiscripts/run_onchange_after_05-update-cargo-crates.sh.tmpl`](../../../../home/.chezmoiscripts/run_onchange_after_05-update-cargo-crates.sh.tmpl)

This hook installs missing crates and uninstalls crates not in the list.

## Go tools

- List: [`home/readonly_dot_default-golang-pkgs.tmpl`](../../../../home/readonly_dot_default-golang-pkgs.tmpl) (template; supports `.isWork` scoping)
- Installed as: `~/.default-golang-pkgs`
- Hook: [`home/.chezmoiscripts/run_onchange_after_05-update-golang-pkgs.sh.tmpl`](../../../../home/.chezmoiscripts/run_onchange_after_05-update-golang-pkgs.sh.tmpl)
- Reconcile helper: [`scripts/reconcile_golang_pkgs.py`](../../../../scripts/reconcile_golang_pkgs.py)

This hook installs missing tools and reconciles installed binaries against the list: when a module is removed, its binary is deleted from `GOBIN`. A state ledger (`~/.cache/chezmoi/golang-pkgs-state`) ensures only binaries this tooling installed are removed; hand-installed Go binaries are left untouched. See [Add A Go Tool](./go.md) for details.

## Ruby gems

- List: [`home/readonly_dot_default-gems`](../../../../home/readonly_dot_default-gems)
- Installed as: `~/.default-gems`
- Hook: [`home/.chezmoiscripts/run_onchange_after_05-update-gems.sh.tmpl`](../../../../home/.chezmoiscripts/run_onchange_after_05-update-gems.sh.tmpl)

## Global yarn packages

- List: [`home/readonly_dot_default-yarn-pkgs`](../../../../home/readonly_dot_default-yarn-pkgs)
- Installed as: `~/.default-yarn-pkgs`
- Hook: [`home/.chezmoiscripts/run_onchange_after_05-update-yarn-pkgs.sh.tmpl`](../../../../home/.chezmoiscripts/run_onchange_after_05-update-yarn-pkgs.sh.tmpl)
- Manual command: [`home/exact_bin/executable_,install-yarn-pkgs`](../../../../home/exact_bin/executable_,install-yarn-pkgs)

The `,install-yarn-pkgs` command installs missing listed packages, uninstalls packages no longer listed, then runs `yarn global upgrade --latest`. This keeps managed globals current even when Yarn's recorded semver range would otherwise stay on an older `0.x` minor.

This list now includes some AI tooling that used to be managed elsewhere. Pi-related globals such as `@earendil-works/pi-coding-agent`, `@earendil-works/pi-tui`, and `pi-mcp-adapter` are kept here; Pi settings reference the yarn global `node_modules` path for `pi-mcp-adapter` so Pi itself does not try to manage extension updates via npm.

If you do not want global yarn packages, keep the list empty.

## uv (Python versions + global tools)

Python versions:

- File: [`home/readonly_dot_python-version`](../../../../home/readonly_dot_python-version)
- Installed as: `~/.python-version`
- Hook: [`home/.chezmoiscripts/run_onchange_after_05-install-uv-versions.sh.tmpl`](../../../../home/.chezmoiscripts/run_onchange_after_05-install-uv-versions.sh.tmpl)

Global tools:

- Template: [`home/readonly_dot_default-uv-tools.tmpl`](../../../../home/readonly_dot_default-uv-tools.tmpl)
- Installed as: `~/.default-uv-tools`
- Hook: [`home/.chezmoiscripts/run_onchange_after_06-update-uv-tools.sh.tmpl`](../../../../home/.chezmoiscripts/run_onchange_after_06-update-uv-tools.sh.tmpl)

## GitHub CLI extensions

- Hook: [`home/.chezmoiscripts/run_onchange_after_05-install-gh-extensions.fish.tmpl`](../../../../home/.chezmoiscripts/run_onchange_after_05-install-gh-extensions.fish.tmpl)

This keeps a managed list of extensions installed and removes extensions that are no longer listed.

## Manual packages (GitHub releases / DMGs)

Some tools and apps are installed from GitHub releases.

- List template: [`home/readonly_dot_default-custom-packages.tmpl`](../../../../home/readonly_dot_default-custom-packages.tmpl)
- Installed as: `~/.default-custom-packages`
- Installer: [`home/.chezmoiscripts/run_onchange_after_05-install-custom-packages.sh.tmpl`](../../../../home/.chezmoiscripts/run_onchange_after_05-install-custom-packages.sh.tmpl)

That installer supports:

- DMG apps copied to `/Applications`
- single-file binaries into `$HOME/.local/bin`
- `.tar.gz` archives with a single binary

Use this for tools that are not available in Homebrew or when you need to pin a specific release asset.

It also downloads a couple extra tools directly inside the installer.

At the moment, that includes:

- `ytsurf` (downloaded into `~/.local/bin`)
- `amp` (installed via its upstream install script if not already present)

## Verification And Troubleshooting

High-signal checks:

```bash
brew bundle check --global
mise ls --current
uv tool list
yarn global list
```

If a package disappeared unexpectedly after apply:

- check whether it is declared in the correct source list/template.
- check whether the corresponding hook ran successfully.
- for Homebrew specifically, remember `brew bundle cleanup --global --force` removes entries not present in the Brewfile.

## Related

- [Add a Homebrew package](homebrew.md)
- [Add a custom package](custom.md)
- Pin a tool version (mise): edit [`home/dot_config/mise/config.toml.tmpl`](../../../../home/dot_config/mise/config.toml.tmpl) and run `chezmoi apply`.
- [Add a Cargo crate](cargo.md)
- [Add a Go tool](go.md)
- [Add a Ruby gem](ruby.md)
- [Add a global yarn package](yarn.md)
- [Add a uv tool](uv.md)
- [Add a GitHub CLI extension](../../workflow/git-identity/gh-extension.md)
- [Updating](../chezmoi/update.md)
