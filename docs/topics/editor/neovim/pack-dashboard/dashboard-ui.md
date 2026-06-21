---
sidebar_position: 2
title: Dashboard UI
---

# Dashboard UI

## Dashboard rows

| Signal        | Meaning                                                                    | Action                                                                                |
| ------------- | -------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| update        | Remote has a pending update                                                | `<CR>` for one, `u` for selected, `U` for visible/all                                 |
| orphan        | Installed pack is no longer declared                                       | `C` cleans selected or all orphans after confirmation                                 |
| drift         | On-disk checkout no longer satisfies the spec version                      | `V` heals drift offline with `vim.pack.update(..., { offline = true, force = true })` |
| risky         | `version = "*"` would select a non-release tag that outranks real releases | Switch to `version = false` or an explicit range/tag                                  |
| breaking risk | Semver major bump or commit-message breaking markers                       | Inspect details before updating                                                       |
| error         | Fetch/status/checkout failed                                               | Open details; the failure text is colorized                                           |

Rows can be selected with `<Space>` / `x` or visual mode. Selection state is separate from the risk column so a queued update does not look like a breaking-risk row.

## Details popup

`K` opens the details popup for the current row.

For pending updates it shows one line per pending commit. Commits carrying breaking markers are highlighted, including markers in the commit body such as `BREAKING CHANGE:`. If a row is classified as breaking only because of semver-major movement, the header shows a warning banner so the details never silently contradict the row.

Inside the details popup:

| Key | Action                                       |
| --- | -------------------------------------------- |
| `o` | Open the single commit under the cursor      |
| `O` | Open the compare URL for all pending commits |
| `r` | Open the plugin repository                   |
