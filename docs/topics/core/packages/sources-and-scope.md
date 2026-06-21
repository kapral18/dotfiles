---
sidebar_position: 1
title: Sources and scope
---

# Sources and scope

Package managers are split by source-of-truth and by whether they can branch on `.isWork`.

## Package sources at a glance

| Source                        | List file                                                                                                                                                        | Hook                                                    | Scoped |
| ----------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------- | ------ |
| Homebrew                      | [`home/.chezmoitemplates/brews/`](../../../../home/.chezmoitemplates/brews/) -> [`home/readonly_dot_Brewfile.tmpl`](../../../../home/readonly_dot_Brewfile.tmpl) | `run_onchange_after_03-install-brew-packages.fish.tmpl` | Yes    |
| mise                          | [`home/dot_config/mise/config.toml.tmpl`](../../../../home/dot_config/mise/config.toml.tmpl)                                                                     | `run_onchange_after_05-install-mise-runtimes.sh.tmpl`   | Yes    |
| Cargo                         | [`home/readonly_dot_default-cargo-crates`](../../../../home/readonly_dot_default-cargo-crates)                                                                   | `run_onchange_after_05-update-cargo-crates.sh.tmpl`     | No     |
| Go                            | [`home/readonly_dot_default-golang-pkgs.tmpl`](../../../../home/readonly_dot_default-golang-pkgs.tmpl)                                                           | `run_onchange_after_05-update-golang-pkgs.sh.tmpl`      | Yes    |
| Ruby gems                     | [`home/readonly_dot_default-gems`](../../../../home/readonly_dot_default-gems)                                                                                   | `run_onchange_after_05-update-gems.sh.tmpl`             | No     |
| yarn                          | [`home/readonly_dot_default-yarn-pkgs`](../../../../home/readonly_dot_default-yarn-pkgs)                                                                         | `run_onchange_after_05-update-yarn-pkgs.sh.tmpl`        | No     |
| uv Python versions            | [`home/readonly_dot_python-version`](../../../../home/readonly_dot_python-version)                                                                               | `run_onchange_after_05-install-uv-versions.sh.tmpl`     | No     |
| uv tools                      | [`home/readonly_dot_default-uv-tools.tmpl`](../../../../home/readonly_dot_default-uv-tools.tmpl)                                                                 | `run_onchange_after_06-update-uv-tools.sh.tmpl`         | Yes    |
| gh extensions                 | managed list in hook                                                                                                                                             | `run_onchange_after_05-install-gh-extensions.fish.tmpl` | n/a    |
| Custom GitHub/source packages | [`home/readonly_dot_default-custom-packages.tmpl`](../../../../home/readonly_dot_default-custom-packages.tmpl)                                                   | `run_onchange_after_05-install-custom-packages.sh.tmpl` | Yes    |

All hooks live under [`home/.chezmoiscripts/`](../../../../home/.chezmoiscripts/).

## Scope-aware package lists

| Source            | Scoping model                                                                                                          |
| ----------------- | ---------------------------------------------------------------------------------------------------------------------- |
| Homebrew          | per-category partials under `brews/shared/`, `brews/personal/`, and `brews/work/`; profile membership is the directory |
| Go                | template conditionals in `readonly_dot_default-golang-pkgs.tmpl`                                                       |
| uv Python         | shared `.python-version` list                                                                                          |
| uv tools          | template conditionals in `readonly_dot_default-uv-tools.tmpl`                                                          |
| Custom packages   | template conditionals in `readonly_dot_default-custom-packages.tmpl`                                                   |
| Shared everywhere | Cargo crates, yarn globals, Ruby gems                                                                                  |

Example personal-only Go entry:

```gotemplate
{{ if ne .isWork true }}
github.com/owner/personal-only-tool
{{ end -}}
```
