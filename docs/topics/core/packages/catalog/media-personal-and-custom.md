---
sidebar_position: 5
title: Media, personal tools, and custom releases
---

# Media, personal tools, and custom releases

This slice covers media processing, personal tools, and tools installed from GitHub releases because they do not fit a higher-priority package manager.

## Audio, video, and image tools

| Tool                                                                                                                                                                            | Source | Why it is here                          |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ | --------------------------------------- |
| [`imagemagick`](https://imagemagick.org/index.php)                                                                                                                              | `brew` | image conversion/manipulation           |
| [`sox`](https://sox.sourceforge.net/), [`switchaudio-osx`](https://github.com/deweller/switchaudio-osx/)                                                                        | `brew` | audio processing and device switching   |
| [`yt-dlp`](https://github.com/yt-dlp/yt-dlp), [`lazycut`](https://github.com/ozemin/lazycut), [`nano-ffmpeg`](https://github.com/dgr8akki/nano-ffmpeg), [`mpv`](https://mpv.io) | `brew` | video download/playback/cutting helpers |
| [`chafa`](https://hpjansson.org/chafa/), [`imgcat`](https://github.com/eddieantonio/imgcat)                                                                                     | `brew` | terminal image rendering                |
| [`cmus`](https://cmus.github.io/)                                                                                                                                               | `brew` | terminal music player                   |
| [`bookokrat`](https://bugzmanov.github.io/bookokrat/index.html)                                                                                                                 | `brew` | media/reading utility                   |

## Presentation and content tools

| Tool                                                                                                                                                | Source                     | Why it is here                                         |
| --------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------- | ------------------------------------------------------ |
| [`freeze`](https://github.com/charmbracelet/freeze), [`glow`](https://github.com/charmbracelet/glow), [`gum`](https://github.com/charmbracelet/gum) | `brew` / Charmbracelet tap | generated terminal visuals, markdown, scripted prompts |
| [`cast-text`](https://github.com/piqoni/cast-text)                                                                                                  | `brew`                     | presentation/content helper                            |
| [`youplot`](https://github.com/red-data-tools/YouPlot/)                                                                                             | `brew`                     | quick terminal plots                                   |
| [`terminaltexteffects`](https://github.com/ChrisBuilds/terminaltexteffects)                                                                         | `uv`                       | animated terminal text output                          |

## Custom GitHub releases

| Tool/app                                                 | Source              | Why it is here                        |
| -------------------------------------------------------- | ------------------- | ------------------------------------- |
| [FluidVoice](https://github.com/altic-dev/FluidVoice)    | `custom dmg`        | macOS app from GitHub releases        |
| [Squirrel Disk](https://github.com/adileo/squirreldisk)  | `custom dmg`        | disk utility app from GitHub releases |
| [`mdtt`](https://github.com/szktkfm/mdtt)                | `custom tar_gz_bin` | release binary archive                |
| [`kitten`](https://github.com/kovidgoyal/kitty)          | `custom file`       | kitty CLI for image preview support   |
| [`enola`](https://github.com/TheYahya/enola)             | `custom tar_gz_bin` | terminal utility release binary       |
| [sd-cli](https://github.com/leejet/stable-diffusion.cpp) | `custom zip_opt`    | Metal runner for `,image-local`       |

## Other apps and tools

| Tool                                                 | Source | Why it is here                            |
| ---------------------------------------------------- | ------ | ----------------------------------------- |
| [`tele`](https://github.com/sorokin-vladimir/tele)   | `brew` | personal Telegram TUI, launched via `,tg` |
| [`kanban-tui`](https://github.com/Zaloog/kanban-tui) | `uv`   | terminal task board                       |
