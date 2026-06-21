---
sidebar_position: 1
title: Loading and version policy
---

# Loading and version policy

## Loading model

Plugin specs are still declared in lazy-style tables, but loading is trigger-aware in `core/plugins.lua`: `cmd`, `event`, `ft`, and key-triggered plugins are deferred until first use while always-on specs load at startup.

`inc-rename.nvim` is loaded on `LspAttach` rather than `cmd = IncRename`. The deferred command stub in `core/plugins.lua` re-executes commands with `vim.cmd()`, which breaks Neovim's command-preview API that `inc-rename` relies on.

Orphan cleanup only removes directories for plugins that are no longer present in the merged Lua specs. Plugins skipped at startup because `cond` is false still count as managed packs, so their install is not deleted and re-fetched on the next session.

## Version policy

Startup does not probe remotes. Instead, `PackSync` and `PackStatus` refresh a cached heuristic map under `stdpath("state")` that decides per plugin whether to follow release tags or branch tip.

| Spec field                              | Meaning                                                                      |
| --------------------------------------- | ---------------------------------------------------------------------------- |
| `version = "*"`                         | Latest semver tag. Watch for upstream non-release tags that parse as semver. |
| `version = "^1.0"`, `"~1.2"`, `">=2.3"` | Greatest matching semver tag                                                 |
| `version = "v1.2.3"`                    | Exact tag                                                                    |
| `version = "<commit-sha>"`              | Exact commit                                                                 |
| `version = false`                       | Default branch tip; skip tag resolution                                      |
| omitted `version`                       | Use the cached heuristic                                                     |
| `commit`, `tag`, `branch`               | Take priority over `version`                                                 |

The heuristic uses three gates when `version` is omitted:

1. Minimum release history: repos with fewer than 3 semver tags fall back to branch tip if more than 30 commits have landed since the last tag.
2. Commit ratio: if commits since the latest tag exceed average commits per release by 1.5x, fall back to branch tip.
3. Absolute cap: more than 150 unreleased commits always means branch tip.

Run `:PackPolicyRebuild` to clear and recompute the cached heuristic. Pass a plugin name to rebuild just one entry.
