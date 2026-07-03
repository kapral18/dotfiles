---
sidebar_position: 1
---

# Custom Commands

This setup ships small, purpose-built commands into `~/bin`. Anything named `home/exact_bin/executable_,name` becomes a command called `,name`; larger commands keep that public launcher and put private implementation files under `~/lib/,name/`.

![Command palette popup over the tmux workbench, indexing tmux bindings, git aliases, and custom comma commands](../tmux/assets/command-palette-full.png)

## How to discover them

```bash
ls -1 "$HOME/bin" | rg '^,'
command -v ,w
,w --help
```

The fastest visual entry point is the tmux command palette: `prefix` + `r`. It indexes comma commands, tmux bindings, git aliases, and optional drop-in entries.

## Command families

| Family               | Use it for                                                                                 | Details                                                                                 |
| -------------------- | ------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------- |
| Health and readiness | `,doctor`, `,kbn-pr-audit`                                                                 | [High-leverage commands](./high-leverage.md)                                            |
| Worktrees and GitHub | `,w`, `,gh-worktree`, `,gh-prw`, `,gh-issuew`, `,gh-tfork`                                 | [High-leverage commands](./high-leverage.md), [Worktrees](../git-identity/worktrees.md) |
| Patch/file transfer  | `,wh`, `,add-patch-to-prs`                                                                 | [High-leverage commands](./high-leverage.md)                                            |
| tmux helpers         | `,tmux-run-all`, `,tmux-lowfi`                                                             | [High-leverage commands](./high-leverage.md), [Tmux](../tmux/index.md)                  |
| Search and discovery | `,grepo`, `,fuzzy-brew-search`, `,search-gh-topic`, `,youtube-search`                      | [Command catalog](./catalog.md)                                                         |
| Testing and analysis | `,jest-test-title-report`, `,get-risky-tests`, `,get-age-buckets`, `,generate-git-sandbox` | [Command catalog](./catalog.md)                                                         |
| AI and agents        | `,agent-memory`, `,artifact`, `,ai-kb`, `,ralph`, provider wrappers                        | [Command catalog](./catalog.md), [Agentic OS](../../ai-assistants/index.md)             |
| Utility / plumbing   | `,bat-preview`, `,fzf-*`, `,history-sync`, media helpers                                   | [Command catalog](./catalog.md)                                                         |

## Source and coverage contract

| Surface             | Source                                                                               |
| ------------------- | ------------------------------------------------------------------------------------ |
| Commands            | [`home/exact_bin/`](../../../../home/exact_bin/)                                     |
| Fish completions    | [`home/dot_config/fish/completions/`](../../../../home/dot_config/fish/completions/) |
| Command internals   | [`home/exact_lib/exact_,<name>/`](../../../../home/exact_lib/)                       |
| Shared command libs | [`home/exact_lib/exact_shared/`](../../../../home/exact_lib/exact_shared/)           |
| Catalog diagram     | [`.mermaids/07c-bin-commands.mmd`](../../../../.mermaids/07c-bin-commands.mmd)       |
| Surface verifier    | [`scripts/verify_bin_surface.py`](../../../../scripts/verify_bin_surface.py)         |

New `~/bin` commands must have a Fish completion, docs coverage, and `.mermaids/07c-bin-commands.mmd` coverage. Large or multi-module commands should move internals to `home/exact_lib/exact_,<name>/`; shared helpers belong under `home/exact_lib/exact_shared/`. `make verify-bin-surface` checks that command-library directories are not orphaned.

## Related

- [High-leverage commands](./high-leverage.md)
- [Command catalog](./catalog.md)
- [Worktree workflow](../git-identity/worktrees.md)
- [Ralph orchestrator](../../ai-assistants/ralph/index.md)
- [Reference map](../../../reference/reference-map.md)
