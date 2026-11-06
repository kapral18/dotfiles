---
sidebar_position: 3
title: Terminal, files, and data
---

# Terminal, files, and data

This slice is the day-to-day terminal toolbox: shells, herdr, file navigation, fuzzy search, structured data, databases, and docs readers.

## Shells, prompts, and terminal orchestration

| Tool                                                                          | Source | Why it is here                               |
| ----------------------------------------------------------------------------- | ------ | -------------------------------------------- |
| [`fish`](https://fishshell.com), [`bash`](https://www.gnu.org/software/bash/) | `brew` | managed shell environments                   |
| [`fish-lsp`](https://www.fish-lsp.dev)                                        | `brew` | language server for fish configs/completions |
| [`starship`](https://starship.rs/)                                            | `brew` | prompt                                       |
| [`herdr`](https://github.com/herdrdev/herdr)                                  | `brew` | terminal workbench and popup surface         |
| [`dekit`](https://github.com/pvolok/dekit)                                    | `brew` | multi-process terminal runner                |
| [`ghostty`](https://ghostty.org/)                                             | `cask` | terminal app                                 |

## File navigation, search, and cleanup

| Tool                                                                                                                                                                                              | Source   | Why it is here                                 |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- | ---------------------------------------------- |
| [`bat`](https://github.com/sharkdp/bat), [`lsd`](https://github.com/lsd-rs/lsd), [`tree`](https://oldmanprogrammer.net/source.php?dir=projects/tree)                                              | `brew`   | readable file listing/preview                  |
| [`yazi`](https://yazi-rs.github.io), [`zoxide`](https://github.com/ajeetdsouza/zoxide)                                                                                                            | `brew`   | file manager and smart directory jumping       |
| [`fd`](https://github.com/sharkdp/fd), [`findutils`](https://www.gnu.org/software/findutils/), [`fzf`](https://junegunn.github.io/fzf/), [`ripgrep-all`](https://github.com/phiresky/ripgrep-all) | `brew`   | search/fuzzy-find core                         |
| [`kitten`](https://github.com/kovidgoyal/kitty)                                                                                                                                                   | `custom` | kitty CLI used for image previews in fzf flows |

## Structured data and databases

| Tool                                                                          | Source | Why it is here                      |
| ----------------------------------------------------------------------------- | ------ | ----------------------------------- |
| [`jq`](https://jqlang.github.io/jq/), [`yq`](https://github.com/mikefarah/yq) | `brew` | JSON/YAML query and TUI exploration |
| [`sheets`](https://github.com/maaslalani/sheets)                              | `brew` | spreadsheet workflows               |
| [`rainfrog`](https://github.com/achristmascarl/rainfrog)                      | `brew` | database TUIs                       |

## Docs and knowledge in the terminal

| Tool                                                                                                                                | Source | Why it is here                               |
| ----------------------------------------------------------------------------------------------------------------------------------- | ------ | -------------------------------------------- |
| [`tealdeer`](https://tealdeer-rs.github.io/tealdeer/)                                                                               | `brew` | tldr pages                                   |
| [`circumflex`](https://github.com/bensadeh/circumflex)                                                                              | `brew` | Hacker News terminal reader                  |
| [`mandown`](https://github.com/Titor8115/mandown), [`treemd`](https://github.com/epistates/treemd), [`pandoc`](https://pandoc.org/) | `brew` | markdown/docs conversion and viewing         |
| [`lychee`](https://lychee.cli.rs/)                                                                                                  | `brew` | link checking and leak detection around docs |
