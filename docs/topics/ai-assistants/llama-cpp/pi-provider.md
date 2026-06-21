---
sidebar_position: 3
title: Pi provider
---

# Pi provider

Pi settings and models are installed readonly, so the llama.cpp provider is declared once in shared chezmoi source and rendered into `~/.pi/agent/models.json` for both profiles:

- Shared source: [`home/dot_pi/agent/readonly_models.json`](../../../../home/dot_pi/agent/readonly_models.json)
- Work source: [`scripts/generate_pi_models.py`](../../../../scripts/generate_pi_models.py) starts from that shared source, then adds work-only LiteLLM and Azure providers

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

Work LiteLLM/Azure keys use `$ENV_VAR` syntax. Pi's startup migration therefore has nothing to rewrite and never attempts to write the read-only `~/.pi/agent/models.json`.

If `llama-server` starts with `--api-key`, export `LLAMA_CPP_API_KEY` before launching Pi.
