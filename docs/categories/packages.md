# Packages

Back: [`docs/categories/index.md`](index.md)

This setup treats package installation as declarative.

That means:

- you edit a list (Brewfile / cargo crates / go pkgs / gems / npm / uv tools)
- you run `chezmoi apply`
- hooks install missing items and (in some systems) remove items no longer
  listed

The core workflow is:

1. Edit the list file in `home/`
2. Run `chezmoi apply`
3. Verify the tool is installed / available

## Homebrew (Brewfile)

- Source: `home/readonly_dot_Brewfile.tmpl`
- Installed as: `~/.Brewfile`
- Hook: `home/.chezmoiscripts/run_onchange_after_03-install-brew-packages.fish.tmpl`

The hook runs:

- `brew bundle cleanup --global --force`
- `brew bundle --global`

So the Brewfile acts like the source-of-truth.

If you are new to this style: it is closer to "infrastructure as code" than
"I installed a thing once".

## ASDF (Tool Versions)

- Plugins list: `home/asdf_plugins.tmpl`
- Version pins: `home/readonly_dot_tool-versions.tmpl`
- Installed as: `~/.tool-versions`
- Hook: `home/.chezmoiscripts/run_onchange_after_05-install-asdf-plugins.sh.tmpl`

That hook:

- installs plugins listed in the template
- removes plugins not listed
- installs tool versions listed in the rendered `.tool-versions`
- uninstalls versions that are no longer wanted

If you only adopt one idea from this setup, make it this: pin your tool versions
so projects behave consistently across machines.

## Cargo crates

- List: `home/readonly_dot_default-cargo-crates`
- Installed as: `~/.default-cargo-crates`
- Hook: `home/.chezmoiscripts/run_onchange_after_05-update-cargo-crates.sh.tmpl`

This hook installs missing crates and uninstalls crates not in the list.

## Go tools

- List: `home/readonly_dot_default-golang-pkgs`
- Installed as: `~/.default-golang-pkgs`
- Hook: `home/.chezmoiscripts/run_onchange_after_05-update-golang-pkgs.sh.tmpl`

This hook installs missing tools and attempts to clean up unused packages.

## Ruby gems

- List: `home/readonly_dot_default-gems`
- Installed as: `~/.default-gems`
- Hook: `home/.chezmoiscripts/run_onchange_after_05-update-gems.sh.tmpl`

## Global npm packages

- List: `home/readonly_dot_default-npm-pkgs`
- Installed as: `~/.default-npm-pkgs`
- Hook: `home/.chezmoiscripts/run_onchange_after_05-update-npm-pkgs.sh.tmpl`
- Manual command: `home/exact_bin/executable_,install-npm-pkgs`

The `,install-npm-pkgs` command installs packages in the list and reshims
`nodejs` in ASDF.

If you do not want global npm packages, keep the list empty.

## uv (Python versions + global tools)

Python versions:

- File: `home/readonly_dot_python-version`
- Installed as: `~/.python-version`
- Hook: `home/.chezmoiscripts/run_onchange_after_05-install-uv-versions.sh.tmpl`

Global tools:

- Template: `home/readonly_dot_default-uv-tools.tmpl`
- Installed as: `~/.default-uv-tools`
- Hook: `home/.chezmoiscripts/run_onchange_after_06-update-uv-tools.sh.tmpl`

## GitHub CLI extensions

- Hook: `home/.chezmoiscripts/run_onchange_after_05-install-gh-extensions.fish.tmpl`

This keeps a managed list of extensions installed and removes extensions that
are no longer listed.

## Manual packages (GitHub releases / DMGs)

Some tools and apps are installed from GitHub releases.

- List template: `home/readonly_dot_default-manual-packages.tmpl`
- Installed as: `~/.default-manual-packages`
- Installer: `home/.chezmoiscripts/run_onchange_after_05-install-manual-packages.sh.tmpl`

That installer supports:

- DMG apps copied to `/Applications`
- single-file binaries into `$HOME/.local/bin`
- `.tar.gz` archives with a single binary

Use this for tools that are not available in Homebrew or when you need to pin a
specific release asset.

It also downloads a couple extra tools directly inside the installer.

At the moment, that includes:

- `ytsurf` (downloaded into `~/.local/bin`)
- `amp` (installed via its upstream install script if not already present)

## Verification And Troubleshooting

High-signal checks:

```bash
brew bundle check --global
asdf current
uv tool list
npm --global --silent ls
```

If a package disappeared unexpectedly after apply:

- check whether it is declared in the correct source list/template.
- check whether the corresponding hook ran successfully.
- for Homebrew specifically, remember `brew bundle cleanup --global --force`
  removes entries not present in the Brewfile.

## Related

- Add a Homebrew package: [`docs/recipes/add-a-homebrew-package.md`](../recipes/add-a-homebrew-package.md)
- Add a manual package: [`docs/recipes/add-a-manual-package.md`](../recipes/add-a-manual-package.md)
- Pin a tool version (ASDF): [`docs/recipes/pin-a-tool-version-asdf.md`](../recipes/pin-a-tool-version-asdf.md)
- Add a Cargo crate: [`docs/recipes/add-a-cargo-crate.md`](../recipes/add-a-cargo-crate.md)
- Add a Go tool: [`docs/recipes/add-a-go-tool.md`](../recipes/add-a-go-tool.md)
- Add a Ruby gem: [`docs/recipes/add-a-ruby-gem.md`](../recipes/add-a-ruby-gem.md)
- Add a global npm package: [`docs/recipes/add-a-global-npm-package.md`](../recipes/add-a-global-npm-package.md)
- Add a uv tool: [`docs/recipes/add-a-uv-tool.md`](../recipes/add-a-uv-tool.md)
- Add a GitHub CLI extension: [`docs/recipes/add-a-gh-extension.md`](../recipes/add-a-gh-extension.md)
- Updating: [`docs/recipes/updating.md`](../recipes/updating.md)
