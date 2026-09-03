---
sidebar_position: 1
title: AI and agent tooling
---

# AI and agent tooling

The AI package set spans casks, Homebrew formulae, yarn globals, uv tools, custom wrappers, and local model assets.

## Coding agents and harnesses

| Tool                                                                                   | Source             | Why it is here                                                                                                                                                    |
| -------------------------------------------------------------------------------------- | ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`cursor-cli`](https://cursor.com/)                                                    | official installer | Cursor command-line harness, installed via `cursor.com/install` (unsupported as a Homebrew cask)                                                                  |
| [`copilot-cli`](https://docs.github.com/en/copilot/concepts/agents/about-copilot-cli)  | `cask`             | GitHub Copilot CLI harness, custom agents, hooks, and MCP config target                                                                                           |
| [`@openai/codex`](https://github.com/openai/codex)                                     | `yarn`             | Codex CLI; an `@install-priority-exception` keeps it on Yarn because the Homebrew cask lags upstream releases                                                     |
| [`codex-app`](https://chatgpt.com/codex?app-landing-page=true)                         | `cask`             | Codex desktop app (`Codex.app`); Homebrew marks the standalone cask deprecated, while `codex app` is the supported CLI installer                                  |
| [`claude`](https://claude.com/download)                                                | `cask`             | Anthropic Claude desktop app (`Claude.app`)                                                                                                                       |
| [`opencode`](https://opencode.ai)                                                      | `brew`             | OpenCode CLI/TUI with profile merge and MCP wiring                                                                                                                |
| [`antigravity-cli`](https://github.com/google-antigravity/antigravity-cli)             | `cask`             | Google Antigravity terminal coding-agent harness, launched as `agy`; the Brew hook clears a prior standalone binary and partial cask receipt before first install |
| [`antigravity`](https://antigravity.google/product/antigravity-2)                      | `cask`             | Google Antigravity desktop agent orchestration platform (`Antigravity.app`)                                                                                       |
| [`@anthropic-ai/claude-code`](https://www.npmjs.com/package/@anthropic-ai/claude-code) | `yarn`             | Claude Code CLI outside Homebrew cask management                                                                                                                  |
| [`@earendil-works/pi-coding-agent`](https://pi.dev/)                                   | `yarn`             | Pi coding agent CLI                                                                                                                                               |
| [`@earendil-works/pi-tui`](https://pi.dev/)                                            | `yarn`             | Pi terminal UI package                                                                                                                                            |
| [`playwriter`](https://github.com/remorses/playwriter)                                 | `yarn`             | browser-control/code-generation agent package                                                                                                                     |
| [`freebuff`](https://freebuff.com/get-started)                                         | `yarn`             | free coding agent CLI                                                                                                                                             |

## Agent extensions and support packages

| Tool                                                                        | Source                  | Why it is here                                               |
| --------------------------------------------------------------------------- | ----------------------- | ------------------------------------------------------------ |
| [`pi-mcp-adapter`](https://github.com/nicobailon/pi-mcp-adapter)            | `yarn`                  | MCP adapter extension loaded by Pi settings                  |
| [`pi-subagents`](https://github.com/nicobailon/pi-subagents)                | `yarn`                  | subagent delegation extension for Pi child contexts          |
| [`tuicr`](https://github.com/agavra/tuicr)                                  | `brew` tap `agavra/tap` | terminal review UI used around agent diff review flows       |
| [`llmfit`](https://github.com/AlexsJones/llmfit)                            | `brew`                  | AI/model utility in the local toolbox                        |
| [`k-letsfg`](https://github.com/LetsFG/LetsFG)                              | `uv`                    | local flight search CLI exposed through the `k-letsfg` skill |
| [`lexy`](https://github.com/antoniorodr/lexy)                               | `uv git+`               | data/RAG pipeline tool used as a local AI utility            |
| [`terminaltexteffects`](https://github.com/ChrisBuilds/terminaltexteffects) | `uv`                    | terminal text effects for generated/presentation output      |

## Local inference and model assets

| Tool / asset                                                                                                                         | Source   | Why it is here                                                           |
| ------------------------------------------------------------------------------------------------------------------------------------ | -------- | ------------------------------------------------------------------------ |
| [`llama.cpp`](https://llama.app)                                                                                                     | `brew`   | local `llama-server` backend for OpenAI/Anthropic-compatible inference   |
| [`hf`](https://huggingface.co/docs/huggingface_hub/guides/cli)                                                                       | `brew`   | Hugging Face CLI for model downloads                                     |
| [`sd-cli`](https://github.com/leejet/stable-diffusion.cpp)                                                                           | `custom` | Metal runner for `,image-local` (not llama-server)                       |
| [`NVIDIA-Nemotron-3.5-Lightning-30B-A3B-UD-Q4_K_XL.gguf`](https://huggingface.co/unsloth/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-GGUF) | `model`  | Unsloth Nemotron 3.5 Lightning (`nemotron-3.5`)                          |
| [`Qwen3.5-9B-UD-Q4_K_XL.gguf`](https://huggingface.co/unsloth/Qwen3.5-9B-GGUF)                                                       | `model`  | Unsloth Qwen3.5 9B (`qwen3.5-9b`)                                        |
| [`Qwen3.8-27B-UD-Q4_K_XL.gguf`](https://huggingface.co/unsloth/Qwen3.8-27B-GGUF)                                                     | `model`  | Unsloth Qwen3.8 27B (`qwen3.8-27b`, non-thinking `qwen3.8-27b-instruct`) |
| [FLUX.2 klein 9B GGUF](https://huggingface.co/leejet/FLUX.2-klein-9B-GGUF)                                                           | `model`  | On-device `,image-local` generate and edit (~15 GB)                      |

## AI-adjacent review and cleanup tools

| Tool                                                                                                    | Source | Why it is here                                            |
| ------------------------------------------------------------------------------------------------------- | ------ | --------------------------------------------------------- |
| [`knip`](https://knip.dev/)                                                                             | `yarn` | unused dependency/export/file analysis for JS/TS projects |
| [`jscpd`](https://jscpd.dev/)                                                                           | `brew` | duplicate-code detector required during refactors         |
| [`ast-grep`](https://ast-grep.github.io/)                                                               | `brew` | structural code search/rewrites                           |
| [`serpl`](https://github.com/yassinebridi/serpl), [`scooter`](https://github.com/thomasschafer/scooter) | `brew` | text search/replacement helpers                           |
| [`dangerzone`](https://github.com/freedomofpress/dangerzone)                                            | `cask` | safe document handling on macOS                           |
