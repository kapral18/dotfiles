---
title: llama.cpp Local Inference
---

# llama.cpp Local Inference

[llama.cpp](https://github.com/ggml-org/llama.cpp) provides `llama-server`, a local C/C++ inference server with OpenAI-compatible chat/completions/responses endpoints and Anthropic-compatible `/v1/messages` endpoints. It is the primary local-agentic-coding backend.

Use this section when serving local GGUF models, wiring a local provider into Pi/Claude/Codex/OpenCode, or managing the model router.

| Navigation slice                                | Owns                                                                           |
| ----------------------------------------------- | ------------------------------------------------------------------------------ |
| [Install and models](install-and-models.md)     | Homebrew install, GGUF manifest, opt-in sync hook                              |
| [Router control plane](router-control-plane.md) | `models.ini`, `,llama-cpp serve/status/load/unload`, runtime env               |
| [Pi provider](pi-provider.md)                   | readonly Pi model provider and startup migration behavior                      |
| [Launchers](launchers.md)                       | Codex metadata, `,codex-llama-cpp`, `,opencode-llama-cpp`, `,claude-llama-cpp` |

## Related

- [Add a llama.cpp model](../../core/packages/llama-cpp-model.md) — manifest recipe
- [Model registry & routing](../model-registry.md) — cloud model definitions
- [Ralph orchestrator](../ralph/index.md) — opt-in local models for roles
