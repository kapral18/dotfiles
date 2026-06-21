---
sidebar_position: 5
title: Media, personal tools, and custom releases
---

# Media, personal tools, and custom releases

This slice covers media processing, personal-only tools, and tools installed from GitHub releases or source builds because they do not fit a higher-priority package manager.

## Audio, video, and image tools

| Tool                                                                                                                                                                            | Source          | Why it is here                          |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------- | --------------------------------------- |
| [`imagemagick`](https://imagemagick.org/index.php), [`graphicsmagick`](https://graphicsmagick.sourceforge.io/)                                                                  | `brew`          | image conversion/manipulation           |
| [`sox`](https://sox.sourceforge.net/), [`switchaudio-osx`](https://github.com/deweller/switchaudio-osx/)                                                                        | `brew`          | audio processing and device switching   |
| [`yt-dlp`](https://github.com/yt-dlp/yt-dlp), [`lazycut`](https://github.com/ozemin/lazycut), [`nano-ffmpeg`](https://github.com/dgr8akki/nano-ffmpeg), [`mpv`](https://mpv.io) | `brew`          | video download/playback/cutting helpers |
| [`chafa`](https://hpjansson.org/chafa/), [`imgcat`](https://github.com/eddieantonio/imgcat)                                                                                     | `brew`          | terminal image rendering                |
| [`cmus`](https://cmus.github.io/)                                                                                                                                               | `brew personal` | terminal music player                   |
| [`bookokrat`](https://bugzmanov.github.io/bookokrat/index.html)                                                                                                                 | `brew`          | media/reading utility                   |

## Presentation and content tools

| Tool                                                                                                                                                                                                                                                                                       | Source                     | Why it is here                                                |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------- | ------------------------------------------------------------- |
| [`presenterm`](https://mfontanini.github.io/presenterm/)                                                                                                                                                                                                                                   | `brew`                     | terminal presentations                                        |
| [`vhs`](https://github.com/charmbracelet/vhs), [`freeze`](https://github.com/charmbracelet/freeze), [`glow`](https://github.com/charmbracelet/glow), [`gum`](https://github.com/charmbracelet/gum), [`markscribe`](https://charm.sh/), [`sequin`](https://github.com/charmbracelet/sequin) | `brew` / Charmbracelet tap | generated terminal visuals, markdown, demos, scripted prompts |
| [`cast-text`](https://github.com/piqoni/cast-text)                                                                                                                                                                                                                                         | `brew personal`            | presentation/content helper                                   |
| [`youplot`](https://github.com/red-data-tools/YouPlot/)                                                                                                                                                                                                                                    | `brew`                     | quick terminal plots                                          |
| [`terminaltexteffects`](https://github.com/ChrisBuilds/terminaltexteffects)                                                                                                                                                                                                                | `uv`                       | animated terminal text output                                 |

## Custom GitHub releases and source builds

| Tool/app                                                 | Source                 | Scope    | Why it is here                        |
| -------------------------------------------------------- | ---------------------- | -------- | ------------------------------------- |
| [FluidVoice](https://github.com/altic-dev/FluidVoice)    | `custom dmg`           | shared   | macOS app from GitHub releases        |
| [Squirrel Disk](https://github.com/adileo/squirreldisk)  | `custom dmg`           | shared   | disk utility app from GitHub releases |
| [`telegramtui`](https://github.com/kapral18/telegramtui) | `custom git_maven_jar` | personal | fork-first Telegram TUI source build  |
| [`mdtt`](https://github.com/szktkfm/mdtt)                | `custom tar_gz_bin`    | shared   | release binary archive                |
| [`dug`](https://github.com/unfrl/dug)                    | `custom file`          | shared   | release binary                        |
| [`kitten`](https://github.com/kovidgoyal/kitty)          | `custom file`          | shared   | kitty CLI for image preview support   |
| [`enola`](https://github.com/TheYahya/enola)             | `custom tar_gz_bin`    | personal | terminal utility release binary       |

## Personal-only apps and tools

| Tool                                                                                                                                                            | Source                 | Why it is here        |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------- | --------------------- |
| [Roblox](https://www.roblox.com/)                                                                                                                               | `cask personal`        | personal app          |
| Telegram TUI stack ([`tdlib`](https://core.telegram.org/tdlib), [`maven`](https://maven.apache.org/), [`telegramtui`](https://github.com/kapral18/telegramtui)) | `brew/custom personal` | personal chat tooling |
| [`kanban-tui`](https://github.com/Zaloog/kanban-tui)                                                                                                            | `uv personal`          | terminal task board   |
