---
sidebar_position: 3
title: Terminal, files, and data
---

# Terminal, files, and data

This slice is the day-to-day terminal toolbox: shells, tmux, file navigation, fuzzy search, structured data, databases, and docs readers.

## Shells, prompts, and terminal orchestration

| Tool                                                                                                               | Source | Why it is here                               |
| ------------------------------------------------------------------------------------------------------------------ | ------ | -------------------------------------------- |
| [`fish`](https://fishshell.com), [`bash`](https://www.gnu.org/software/bash/), [`nushell`](https://www.nushell.sh) | `brew` | managed shell environments                   |
| [`fish-lsp`](https://www.fish-lsp.dev)                                                                             | `brew` | language server for fish configs/completions |
| [`starship`](https://starship.rs/)                                                                                 | `brew` | prompt                                       |
| [`tmux`](https://tmux.github.io/)                                                                                  | `brew` | terminal workbench and popup surface         |
| [`mprocs`](https://github.com/pvolok/mprocs)                                                                       | `brew` | multi-process terminal runner                |
| [`ghostty`](https://ghostty.org/)                                                                                  | `cask` | terminal app                                 |

## File navigation, search, and cleanup

| Tool                                                                                                                                                                                              | Source          | Why it is here                                 |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------- | ---------------------------------------------- |
| [`bat`](https://github.com/sharkdp/bat), [`lsd`](https://github.com/lsd-rs/lsd), [`tree`](https://oldmanprogrammer.net/source.php?dir=projects/tree)                                              | `brew`          | readable file listing/preview                  |
| [`diskonaut`](https://github.com/imsnif/diskonaut), [`dua-cli`](https://lib.rs/crates/dua-cli), [`grandperspective`](https://grandperspectiv.sourceforge.net/)                                    | `brew` / `cask` | disk usage visualization                       |
| [`yazi`](https://yazi-rs.github.io), [`zoxide`](https://github.com/ajeetdsouza/zoxide)                                                                                                            | `brew`          | file manager and smart directory jumping       |
| [`fd`](https://github.com/sharkdp/fd), [`findutils`](https://www.gnu.org/software/findutils/), [`fzf`](https://junegunn.github.io/fzf/), [`ripgrep-all`](https://github.com/phiresky/ripgrep-all) | `brew`          | search/fuzzy-find core                         |
| [`f2`](https://f2.freshman.tech), [`fdupes`](https://github.com/adrianlopezroche/fdupes), [`fclones`](https://github.com/pkolaczk/fclones)                                                        | `brew`          | renaming and duplicate-file cleanup            |
| [`renux`](https://github.com/andrianllmm/renux)                                                                                                                                                   | `uv`            | bulk file renamer TUI                          |
| [`kitten`](https://github.com/kovidgoyal/kitty)                                                                                                                                                   | `custom`        | kitty CLI used for image previews in fzf flows |

## Structured data and databases

| Tool                                                                                                                           | Source   | Why it is here                                   |
| ------------------------------------------------------------------------------------------------------------------------------ | -------- | ------------------------------------------------ |
| [`jq`](https://jqlang.github.io/jq/), [`yq`](https://github.com/mikefarah/yq), [`ijq`](https://codeberg.org/gpanders/ijq)      | `brew`   | JSON/YAML query and TUI exploration              |
| [`fq`](https://github.com/wader/fq), [`jc`](https://github.com/kellyjonbrazil/jc), [`htmlq`](https://github.com/mgdm/htmlq)    | `brew`   | binary/data/HTML conversion and query tools      |
| [`xan`](https://github.com/medialab/xan), [`sheets`](https://github.com/maaslalani/sheets)                                     | `brew`   | CSV/spreadsheet workflows                        |
| [`rainfrog`](https://github.com/achristmascarl/rainfrog), [`lazysql`](https://github.com/jorgerojas26/lazysql)                 | `brew`   | database TUIs                                    |
| [`igrep`](https://github.com/konradsz/igrep), [`nless`](https://github.com/mpryor/nothing-less)                                | `brew`   | interactive grep/less-style data exploration     |
| [`mdtt`](https://github.com/szktkfm/mdtt), [`dug`](https://github.com/unfrl/dug), [`enola`](https://github.com/TheYahya/enola) | `custom` | release-installed terminal data/search utilities |

## Docs and knowledge in the terminal

| Tool                                                                                                                                                                              | Source | Why it is here                               |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ | -------------------------------------------- |
| [`tealdeer`](https://tealdeer-rs.github.io/tealdeer/)                                                                                                                             | `brew` | tldr pages                                   |
| [`circumflex`](https://github.com/bensadeh/circumflex), [`hnterm`](https://hnterm.ggerganov.com), [`reddix`](https://github.com/ck-zhang/reddix)                                  | `brew` | Hacker News / Reddit terminal readers        |
| [`mandown`](https://github.com/Titor8115/mandown), [`treemd`](https://github.com/epistates/treemd), [`pandoc`](https://pandoc.org/), [`doxx`](https://bgreenwell.github.io/doxx/) | `brew` | markdown/docs conversion and viewing         |
| [`lychee`](https://lychee.cli.rs/), [`xleak`](https://github.com/bgreenwell/xleak)                                                                                                | `brew` | link checking and leak detection around docs |
| [`toolong`](https://github.com/Textualize/toolong), [`logmerger`](https://github.com/ptmcg/logmerger)                                                                             | `uv`   | log viewing/merging TUIs                     |
