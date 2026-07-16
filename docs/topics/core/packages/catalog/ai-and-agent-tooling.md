---
sidebar_position: 1
title: AI and agent tooling
---

# AI and agent tooling

The AI package set spans casks, Homebrew formulae, yarn globals, uv tools, custom wrappers, and local model assets.

## Coding agents and harnesses

| Tool                                                                                   | Source             | Why it is here                                                                                   |
| -------------------------------------------------------------------------------------- | ------------------ | ------------------------------------------------------------------------------------------------ |
| [`cursor-cli`](https://cursor.com/)                                                    | official installer | Cursor command-line harness, installed via `cursor.com/install` (unsupported as a Homebrew cask) |
| [`copilot-cli`](https://docs.github.com/en/copilot/concepts/agents/about-copilot-cli)  | `cask`             | GitHub Copilot CLI harness, custom agents, hooks, and MCP config target                          |
| [`codex`](https://github.com/openai/codex)                                             | `cask`             | Codex CLI, exposed through `,codex` with local/cloud provider wrappers                           |
| [`opencode`](https://opencode.ai)                                                      | `brew`             | OpenCode CLI/TUI with profile merge and MCP wiring                                               |
| [`@anthropic-ai/claude-code`](https://www.npmjs.com/package/@anthropic-ai/claude-code) | `yarn`             | Claude Code CLI outside Homebrew cask management                                                 |
| [`@google/gemini-cli`](https://github.com/google-gemini/gemini-cli)                    | `yarn`             | Gemini CLI harness and subagent surface                                                          |
| [`@earendil-works/pi-coding-agent`](https://pi.dev/)                                   | `yarn`             | Pi coding agent CLI                                                                              |
| [`@earendil-works/pi-tui`](https://pi.dev/)                                            | `yarn`             | Pi terminal UI package                                                                           |
| [`playwriter`](https://github.com/remorses/playwriter)                                 | `yarn`             | browser-control/code-generation agent package                                                    |

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

| Tool / asset                                                                                                      | Source  | Why it is here                                                         |
| ----------------------------------------------------------------------------------------------------------------- | ------- | ---------------------------------------------------------------------- |
| [`llama.cpp`](https://llama.app)                                                                                  | `brew`  | local `llama-server` backend for OpenAI/Anthropic-compatible inference |
| [`hf`](https://huggingface.co/docs/huggingface_hub/guides/cli)                                                    | `brew`  | Hugging Face CLI for model downloads                                   |
| [`Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf`](https://huggingface.co/unsloth/Qwen3.6-35B-A3B-GGUF)                          | `model` | primary local GGUF model (`local`)                                     |
| [`Qwen3.6-35B-A3B-abliterated.Q4_K_M.gguf`](https://huggingface.co/mradermacher/Qwen3.6-35B-A3B-abliterated-GGUF) | `model` | refusal-removed sibling (`local-max`)                                  |

## AI-adjacent review and cleanup tools

| Tool                                                                                                    | Source | Why it is here                                            |
| ------------------------------------------------------------------------------------------------------- | ------ | --------------------------------------------------------- |
| [`knip`](https://knip.dev/)                                                                             | `yarn` | unused dependency/export/file analysis for JS/TS projects |
| [`jscpd`](https://jscpd.dev/)                                                                           | `brew` | duplicate-code detector required during refactors         |
| [`ast-grep`](https://ast-grep.github.io/)                                                               | `brew` | structural code search/rewrites                           |
| [`serpl`](https://github.com/yassinebridi/serpl), [`scooter`](https://github.com/thomasschafer/scooter) | `brew` | text search/replacement helpers                           |
| [`dangerzone`](https://github.com/freedomofpress/dangerzone)                                            | `cask` | safe document handling on macOS                           |
