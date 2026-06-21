---
sidebar_position: 4
---

# Tmux: GitHub picker

The GitHub picker is a PR/issue cockpit. It runs as a 95%×95% tmux popup, reads PR and issue sections from its own YAML configs, and renders them in fzf with preview, hierarchy, local worktree markers, review status, and CI state.

Open it with `prefix` + `G`. Press `alt-g` to switch to the [session picker](session-picker.md).

![GitHub picker popup over the natural tmux workbench, with safe demo rows for own PRs, external reviews, issues, epics, pending backports, and a populated preview pane](assets/github-picker-full.png)

## Reading the cockpit

| Area     | Meaning                                                                     |
| -------- | --------------------------------------------------------------------------- |
| Header   | mode, scope, counts, cache age, and primary actions                         |
| Sections | Intent groups: `Action:`, `Mine:`, `Watching:`, `Maintenance:`              |
| Rows     | PRs/issues with review, CI, hierarchy, relation, and local-worktree signals |
| Preview  | Dashboard summary plus PR/issue details, body, activity, and handoff hints  |
| Query    | Search visible labels and hidden status/relation tokens                     |

The screenshot uses safe demo rows so the states are visible without exposing private GitHub data. The UI itself is the real picker launched with `prefix` + `G`.

## Important bindings

| Key                         | Action                                              |
| --------------------------- | --------------------------------------------------- |
| `enter`                     | Checkout worktree and focus it; batches marked rows |
| `tab` / `alt-space`         | Mark/unmark item                                    |
| `ctrl-s`                    | Switch `work` / `home` mode                         |
| `alt-0` / `alt-1` / `alt-2` | Show all / focus / explore scopes                   |
| `alt-n` / `alt-p`           | Jump to next / previous section header              |
| `alt-S`                     | Cycle sort                                          |
| `alt-z` / `alt-Z`           | Collapse family / collapse all                      |
| `alt-M`                     | Mark the current family                             |
| `ctrl-r`                    | Refresh from GitHub                                 |
| `alt-e`                     | Cycle preview expansion                             |
| `alt-A`                     | Hand off selected PRs/issues to Ralph               |
| `alt-x`                     | Open action palette                                 |
| `alt-g`                     | Switch to session picker                            |
| `?`                         | Show help                                           |

`alt-r` is quote-reply here, not refresh. The GitHub picker's `ctrl-r` is already the full refresh path and pre-empts in-flight fetches.

## Sections by intent

| Prefix         | Meaning                                                        |
| -------------- | -------------------------------------------------------------- |
| `Action:`      | You are the bottleneck: review requested, assigned issue, etc. |
| `Mine:`        | You authored it and it is still open                           |
| `Watching:`    | Informational queues, mentions, radar, team views              |
| `Maintenance:` | Special workflows such as pending backports                    |

PRs and issues share the same intent prefixes. The YAML config still splits PR and issue sections for query ergonomics, but the dashboard groups by workflow intent.

## Dashboard scopes

| Scope     | Binding | Includes                             |
| --------- | ------- | ------------------------------------ |
| `all`     | `alt-0` | Every section                        |
| `focus`   | `alt-1` | `Action:` + `Mine:` + `Maintenance:` |
| `explore` | `alt-2` | `Watching:` sections                 |

## Detailed mechanics

The deeper implementation details live in [GitHub picker mechanics](github-picker-mechanics.md):

- data source and cache behavior.
- section jumps and sorting.
- epic/backport/PR-issue hierarchy.
- badges, hidden match tokens, worktree detection.
- comment/review/action helpers and Ralph handoff.
- preview cache and popup sizing.

## Related

- [Session picker](session-picker.md)
- [GitHub picker mechanics](github-picker-mechanics.md)
- [Worktrees](../git-identity/worktrees.md)
- [Ralph orchestrator](../../ai-assistants/ralph/index.md)
