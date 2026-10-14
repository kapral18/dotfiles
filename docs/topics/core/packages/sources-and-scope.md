---
sidebar_position: 1
title: Sources and scope
---

# Sources and scope

Package managers are split by source-of-truth. Template list files can branch on OS or architecture.

## Package sources at a glance

| Source                        | List file                                                                                                                                                        | Hook                                                    | Template |
| ----------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------- | -------- |
| Homebrew                      | [`home/.chezmoitemplates/brews/`](../../../../home/.chezmoitemplates/brews/) -> [`home/readonly_dot_Brewfile.tmpl`](../../../../home/readonly_dot_Brewfile.tmpl) | `run_onchange_after_03-install-brew-packages.fish.tmpl` | Yes      |
| mise                          | [`home/dot_config/mise/config.toml.tmpl`](../../../../home/dot_config/mise/config.toml.tmpl)                                                                     | `run_onchange_after_05-install-mise-runtimes.sh.tmpl`   | Yes      |
| Cargo                         | [`home/readonly_dot_default-cargo-crates`](../../../../home/readonly_dot_default-cargo-crates)                                                                   | `run_onchange_after_05-update-cargo-crates.sh.tmpl`     | No       |
| Go                            | [`home/readonly_dot_default-golang-pkgs.tmpl`](../../../../home/readonly_dot_default-golang-pkgs.tmpl)                                                           | `run_onchange_after_05-update-golang-pkgs.sh.tmpl`      | Yes      |
| Ruby gems                     | [`home/readonly_dot_default-gems`](../../../../home/readonly_dot_default-gems)                                                                                   | `run_onchange_after_05-update-gems.sh.tmpl`             | No       |
| pnpm                          | [`home/readonly_dot_default-pnpm-pkgs`](../../../../home/readonly_dot_default-pnpm-pkgs)                                                                         | `run_onchange_after_05-update-pnpm-pkgs.sh.tmpl`        | No       |
| uv Python versions            | [`home/readonly_dot_python-version`](../../../../home/readonly_dot_python-version)                                                                               | `run_onchange_after_05-install-uv-versions.sh.tmpl`     | No       |
| uv tools                      | [`home/readonly_dot_default-uv-tools.tmpl`](../../../../home/readonly_dot_default-uv-tools.tmpl)                                                                 | `run_onchange_after_06-update-uv-tools.sh.tmpl`         | Yes      |
| gh extensions                 | managed list in hook                                                                                                                                             | `run_onchange_after_05-install-gh-extensions.fish.tmpl` | n/a      |
| Custom GitHub/source packages | [`home/readonly_dot_default-custom-packages.tmpl`](../../../../home/readonly_dot_default-custom-packages.tmpl)                                                   | `run_onchange_after_05-install-custom-packages.sh.tmpl` | Yes      |
| redtab + local Redlib         | pinned in hook; client config [`home/dot_config/redtab/readonly_config.toml`](../../../../home/dot_config/redtab/readonly_config.toml)                           | `run_onchange_after_09-install-redtab.sh.tmpl`          | No       |
| llama.cpp GGUF models         | [`home/readonly_dot_default-llama-cpp-models.tmpl`](../../../../home/readonly_dot_default-llama-cpp-models.tmpl)                                                 | `run_onchange_after_07-sync-llama-cpp-models.sh.tmpl`   | Yes      |
| FLUX.2 klein weights          | [`home/dot_config/sd-image/readonly_models.txt`](../../../../home/dot_config/sd-image/readonly_models.txt)                                                       | none (`,image-local sync` only)                         | No       |

All hooks live under [`home/.chezmoiscripts/`](../../../../home/.chezmoiscripts/).

## redtab and Redlib

[redtab](https://github.com/kapral18/redtab) (private) is a terminal Reddit reader with a tab sidebar, a Home wall of subscribed subreddits, and threaded comments. `old.reddit.com` sends logged-out clients to a login wall, and public Redlib instances serve bot checks, so redtab reads Reddit through a local [Redlib](https://github.com/redlib-org/redlib) container. The hook:

1. Downloads redtab at a pinned commit with `gh api` (the repo is private), builds it with `cargo build --release --locked`, and installs it to `$HOME/.local/bin/redtab`. To ship a new redtab version, bump `REDTAB_COMMIT` in the hook.
2. Starts container `redtab-redlib` with `--restart unless-stopped` on the host:port from `redlib_url` in the client config (`127.0.0.1:8085`). The image is the [Silvenga fork](https://github.com/Silvenga/redlib), pinned by digest; the official image fails with `Failed to create OAuth client` ([redlib#485](https://github.com/redlib-org/redlib/issues/485)).

The hook needs `gh`, `cargo` (mise Rust), and a running Docker. If Docker is not running, it exits non-zero before building, and `chezmoi apply` reports the failure. A failed build leaves the running Redlib alone. The hook sorts last (`09`), so every other hook has already run; start Docker Desktop and re-run `chezmoi apply`. To change the port, edit only `redlib_url`; the hook reads it. The host must stay `127.0.0.1` with a port from 1 to 65535: Docker cannot publish on a hostname, and Redlib stays loopback-only. The hook refuses to render otherwise.

If the container stops, press `S` in redtab: the client config runs `docker start redtab-redlib`. If the container disappears (`docker rm`, a Docker Desktop reset), `chezmoi apply` does not recreate it, because the hook content did not change. Re-run the hook directly:

```bash
chezmoi execute-template --file "$(chezmoi source-path)/.chezmoiscripts/run_onchange_after_09-install-redtab.sh.tmpl" | bash
```

Verify: `curl -s http://127.0.0.1:8085/r/golang/ | grep -c post_title` prints a non-zero count, and `redtab --check` reports Redlib as up. Logs: `docker logs redtab-redlib`.

### Subscriptions

redtab builds its sidebar tabs and Home wall from `~/.config/redtab/subscriptions`: one subreddit per line, `r/` optional; blank lines and `#` comments are ignored. The file is machine-local and not in this repo, so a personal list never reaches the public dotfiles. Edits take effect the next time redtab starts; no `chezmoi apply` is needed. A name with characters other than letters, digits, and `_` makes redtab exit at startup with an error that names the file and the bad name. The list does not follow your Reddit account; update the file when your subscriptions change. `home/.chezmoiignore` lists the file, so `chezmoi add ~/.config/redtab` skips it; `.gitignore` ignores source copies of it under `home/dot_config/redtab/`, so a stray copy is not staged by default.
