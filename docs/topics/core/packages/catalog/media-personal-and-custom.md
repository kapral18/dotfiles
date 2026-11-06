---
sidebar_position: 5
title: Media, personal tools, and custom releases
---

# Media, personal tools, and custom releases

This slice covers media processing, personal tools, and tools installed from GitHub releases because they do not fit a higher-priority package manager.

## Audio, video, and image tools

| Tool                                                                  | Source | Why it is here                  |
| --------------------------------------------------------------------- | ------ | ------------------------------- |
| [`imagemagick`](https://imagemagick.org/index.php)                    | `brew` | image conversion/manipulation   |
| [`switchaudio-osx`](https://github.com/deweller/switchaudio-osx/)     | `brew` | audio device switching          |
| [`yt-dlp`](https://github.com/yt-dlp/yt-dlp), [`mpv`](https://mpv.io) | `brew` | video download/playback helpers |
| [`chafa`](https://hpjansson.org/chafa/)                               | `brew` | terminal image rendering        |
| [`bookokrat`](https://bugzmanov.github.io/bookokrat/index.html)       | `brew` | media/reading utility           |

## Presentation and content tools

| Tool                                                                                           | Source                     | Why it is here             |
| ---------------------------------------------------------------------------------------------- | -------------------------- | -------------------------- |
| [`glow`](https://github.com/charmbracelet/glow), [`gum`](https://github.com/charmbracelet/gum) | `brew` / Charmbracelet tap | markdown, scripted prompts |

## Custom GitHub releases

| Tool/app                                                 | Source           | Why it is here                      |
| -------------------------------------------------------- | ---------------- | ----------------------------------- |
| [`kitten`](https://github.com/kovidgoyal/kitty)          | `custom file`    | kitty CLI for image preview support |
| [sd-cli](https://github.com/leejet/stable-diffusion.cpp) | `custom zip_opt` | Metal runner for `,image-local`     |

## Other apps and tools

| Tool                                               | Source | Why it is here                            |
| -------------------------------------------------- | ------ | ----------------------------------------- |
| [`tele`](https://github.com/sorokin-vladimir/tele) | `brew` | personal Telegram TUI, launched via `,tg` |
