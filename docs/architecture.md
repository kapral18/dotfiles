# Architecture

Back: [`docs/index.md`](index.md)

This setup is a `chezmoi` source directory. `chezmoi` renders templates and
copies files into your `$HOME`.

## Repository Layout

- `home/` is the source-of-truth for files that end up in your home directory.
- `home/.chezmoiscripts/` contains automation hooks that run during apply.
- `home/.chezmoi.toml.tmpl` defines interactive prompts and computed values.
- `home/.chezmoiexternal.toml` pulls a few external assets (git repos/archives).

## Repo-Only Assets (Not Installed Into `$HOME`)

Some directories in `home/` are intentionally ignored by `chezmoi` and are used
as "repo-local data" for scripts.

Ignore rules live in:

- `home/.chezmoiignore`

Examples in this setup:

- `home/app_icons/` is used by the `,apply-app-icons` script, but it is not
  installed into `$HOME`.
- `home/Alfred.alfredpreferences/` is stored in the repo, but not automatically
  applied.

## Chezmoi Naming Conventions (How Source Maps To Installed Files)

Chezmoi uses filename conventions to decide where things land.

Common patterns in this setup:

- `home/dot_config/...` -> `~/.config/...`
- `home/dot_*` -> `~/.<name>` (for example: `home/dot_zsh/` -> `~/.zsh/`)
- `home/private_dot_ssh/...` -> `~/.ssh/...` (and treated as private by chezmoi)
- `executable_foo` -> installs as an executable file named `foo`
- `exact_` prefix in a directory name means "exact directory" (chezmoi does not
  merge it with existing contents)

This is why you may see paths like:

- `home/dot_config/exact_nvim/exact_lua/` in the repo
- but `~/.config/nvim/lua/` on disk

## The Data Flow

This setup is intentionally declarative:

1. You answer prompts in `home/.chezmoi.toml.tmpl`.
2. Templates in `home/` render differently depending on those values.
3. Hooks in `home/.chezmoiscripts/` install / update tools based on the rendered
   config.
4. Re-running `chezmoi apply` converges you back to the intended state.

## Hooks (Automation)

The most important concept for understanding "what happens" is the hook naming:

- `run_once_before_*` runs once before apply work.
- `run_once_after_*` runs once after apply work.
- `run_onchange_after_*` runs after apply _when the tracked inputs change_.

Examples in this repo:

- Xcode CLT: `home/.chezmoiscripts/run_once_before_00-install-xcode.sh`
- Homebrew install: `home/.chezmoiscripts/run_once_after_01-install-brew.sh`
- Fish install: `home/.chezmoiscripts/run_once_after_02-install-fish.sh`
- Brew bundle: `home/.chezmoiscripts/run_onchange_after_03-install-brew-packages.fish.tmpl`
- ASDF plugins + versions: `home/.chezmoiscripts/run_onchange_after_05-install-asdf-plugins.sh.tmpl`

Many hooks embed `sha256sum` comments that reference template content. That is
how the "run on change" behavior is tied to specific files.

## Work vs Personal Split

The primary decision point is the `isWork` prompt in `home/.chezmoi.toml.tmpl`.
It is used to:

- conditionally include certain tools/plugins
- choose which identity config is rendered
- choose which secrets/setup steps run

## External Assets

`home/.chezmoiexternal.toml` is used for things you want updated regularly but
don't want to vendor into your dotfiles repo.

Current externals include:

- tmux plugin manager (`tpm`)
- Hammerspoon spoon: `EmmyLua.spoon`
- `lowfi` data files
- `bat` themes
