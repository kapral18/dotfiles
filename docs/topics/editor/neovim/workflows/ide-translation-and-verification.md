---
sidebar_position: 3
title: IDE translation and verification
---

# IDE translation and verification

## Problems this setup optimizes for

- Fast navigation and editing with a keyboard-first model.
- Tight test loops without leaving the editor.
- Repeatable refactors that update imports/exports predictably.
- Large-repo ergonomics: ownership, ripgrep/fzf tooling, git integration, quickfix lists.

## IDE translation

| IDE concept      | Neovim equivalent                                             |
| ---------------- | ------------------------------------------------------------- |
| Tabs             | Buffers                                                       |
| Problems panel   | Quickfix list                                                 |
| Search panel     | fzf-lua grep/file pickers                                     |
| Project explorer | Neo-tree / Yazi / Oil                                         |
| Multi-cursor     | Available, but motions + operators + textobjects scale better |

If you are used to clicking around panels, start with fzf pickers, quickfix, and one file explorer.

## Verification

```bash
nvim --version
mise ls --current | rg neovim
nvim "+PackSync" +qa
nvim "+checkhealth" +qa
```

Inside Neovim:

- run `:map <leader>tt` and confirm Jest mapping exists.
- open quickfix and test `:QFDedupe`.
- open a git repo file and test `[h` / `]h`.

If keymaps/plugins seem missing, confirm `chezmoi apply` succeeded for `home/dot_config/exact_nvim/`, plugin sync completed, and the active Neovim binary comes from the expected mise version.
