---
sidebar_position: 3
title: Pi provider
---

# Pi provider

Pi settings and models are installed readonly, so the llama.cpp provider is declared in chezmoi source and installed as `~/.pi/agent/models.json` per profile:

- Work source: [`home/dot_pi/agent/readonly_models.json`](../../../../home/dot_pi/agent/readonly_models.json)
- Personal source: [`home/dot_pi/agent/readonly_models.personal.json`](../../../../home/dot_pi/agent/readonly_models.personal.json) declares the same llama.cpp provider

```bash
,llama-cpp serve
pi --model llama-cpp/local       # primary
pi --model llama-cpp/local-max   # abliterated sibling
```

The provider declares both local models:

| Field                  | Value / reason                  |
| ---------------------- | ------------------------------- |
| Models                 | `local`, `local-max`            |
| Base URL               | `http://127.0.0.1:8080/v1`      |
| API mode               | `openai-completions`            |
| Template compatibility | Qwen thinking-compatible        |
| `apiKey`               | `!command` form (`!printf ...`) |

Provider keys use `$ENV_VAR` or `!command` syntax. Pi's startup migration therefore has nothing to rewrite and never attempts to write the read-only `~/.pi/agent/models.json`.

If `llama-server` starts with `--api-key`, export `LLAMA_CPP_API_KEY` before launching Pi.
