---
sidebar_position: 4
title: Launchers
---

# Launchers

These launchers make local llama.cpp models usable from Codex, Cursor, OpenCode, and Claude Code without repeating provider flags every time. Each wrapper solves a different harness-specific problem: Codex needs local model metadata plus provider routing, Cursor needs its OpenAI-compatible `agent-cli-local` flavor, OpenCode needs model ids qualified to its configured provider, and Claude Code needs a llama.cpp-scoped settings file.

All four launchers acquire a shared router lease. They join an existing router, or start a loopback router when none is reachable. After the last managed consumer exits, the auto-started instance stays resident for a 10-minute grace period so the next harness can reuse its loaded model; run `,llama-cpp stop` to end it earlier or set `LLAMA_CPP_GRACE_SECONDS=0` for immediate shutdown. Running `,llama-cpp serve` first remains supported, and that manually started process is left running.

## Mental model

Codex has two layers. The transparent `,codex` wrapper supplies catalog metadata for the llama.cpp router ids, while `,codex-llama-cpp` supplies the provider routing flags that point Codex at `llama-server`.

OpenCode reads providers from `~/.config/opencode/opencode.jsonc`, so its launcher only normalizes model selection and passes the rest through.

Cursor's cloud build rejects local provider flags. `,cursor-llama-cpp` therefore runs the version-matched `agent-cli-local` flavor, pins its provider environment to llama.cpp, and rewrites `-m` to Cursor's `--model` flag.

Claude Code has one global `autoCompactWindow`, but cloud `opus[1m]` and local llama.cpp need different values. The llama.cpp launcher loads an additive settings file with `autoCompactWindow: 200000` and `CLAUDE_CODE_ATTRIBUTION_HEADER=0`, and leaves plain cloud Claude sessions untouched.

## Using it

No separate server command is required for these launchers. Start any harness directly; use `,llama-cpp serve` only when you want the router to remain available independently of harness sessions.

### Codex launcher metadata

Codex only has first-class model metadata for slugs present in its model catalog; unknown local slugs use fallback metadata and emit a warning. This repo ships a transparent `,codex` wrapper plus a small local catalog for the llama.cpp models.

The wrapper injects `-c model_catalog_json="$HOME/.codex/llama-cpp-model-catalog.json"` when the selected model is one of the llama.cpp router ids, in either `--model <id>` or `--model=<id>` form.

Other Codex invocations execute `/opt/homebrew/bin/codex` directly. Hosted MCP authentication is owned by the per-request stdio bridges declared in `~/.codex/config.toml`, not by this launcher.

### Codex launcher (`,codex-llama-cpp`)

The `,codex` shim above only supplies catalog metadata; Codex still needs the provider routing flags to reach llama-server. `,codex-llama-cpp` bakes those in so you don't type them every time.

The wrapper injects:

| Codex config key                     | Value                                           |
| ------------------------------------ | ----------------------------------------------- |
| `model_providers.llama-cpp.base_url` | `http://${LLAMA_CPP_HOST}:${LLAMA_CPP_PORT}/v1` |
| `model_providers.llama-cpp.name`     | `llama.cpp`                                     |
| `model_provider`                     | `llama-cpp`                                     |

The `~/bin/,codex` shim still injects catalog metadata. Pass `--model` / `-m nemotron-3.5` to pick the model.

The wrapper adds its default `--model $CODEX_LLAMA_CPP_MODEL` only when you did not pass one, so there is no duplicate flag.

```bash
,codex-llama-cpp                          # default model nemotron-3.5
,codex-llama-cpp --model qwen3.5-9b       # Unsloth Qwen3.5 9B
,codex-llama-cpp -m qwen3.5-9b exec "..."  # one-shot
```

### Cursor launcher (`,cursor-llama-cpp`)

The launcher uses the same version-matched `agent-cli-local` installation as `,cursor-openrouter`. If that flavor is absent after a Cursor update, the existing `~/lib/,cursor-agent-local/install.sh` installer restores it before launch.

It pins `CURSOR_LOCAL_AGENT_BASE_URL=http://${LLAMA_CPP_HOST}:${LLAMA_CPP_PORT}/v1`, maps `LLAMA_CPP_API_KEY` to `CURSOR_LOCAL_AGENT_API_KEY`, and keeps Cursor's delegated model band on the selected local id. Inherited endpoint and provider credentials cannot redirect the session.

```bash
,cursor-llama-cpp                          # default model nemotron-3.5
,cursor-llama-cpp --model qwen3.5-9b       # Unsloth Qwen3.5 9B
,cursor-llama-cpp -p "summarize README.md" # one-shot
```

### OpenCode launcher (`,opencode-llama-cpp`)

OpenCode reads providers from `~/.config/opencode/opencode.jsonc`; there is no per-invocation provider override.

The `llama-cpp` provider is declared in both profile sources and flows through the merge hook unchanged:

| Field       | Value                      |
| ----------- | -------------------------- |
| Provider id | `llama-cpp`                |
| Base URL    | `http://127.0.0.1:8080/v1` |
| Models      | llama.cpp router ids       |

The provider id avoids a dot (`llama-cpp`, not `llama.cpp`) because OpenCode's SDK derives an incorrect lookup key from dotted ids.

Pass `--model`/`-m` with a bare router id — the wrapper qualifies it to `llama-cpp/<id>` — or the full `llama-cpp/<id>`. With no `--model`, it defaults to `llama-cpp/$OPENCODE_LLAMA_CPP_MODEL` (`nemotron-3.5`).

Any subcommand/args pass through.

```bash
,opencode-llama-cpp                            # interactive TUI, default model nemotron-3.5
,opencode-llama-cpp --model qwen3.5-9b run "…"  # Unsloth Qwen3.5 9B
```

### Claude Code launcher (`,claude-llama-cpp`)

Claude Code compacts conversation history at `autoCompactWindow` tokens.

| Context          | Desired value                                                        |
| ---------------- | -------------------------------------------------------------------- |
| Cloud `opus[1m]` | leave default around 1M                                              |
| Local llama.cpp  | compact below server context so llama.cpp does not reject the prompt |

Those needs conflict on a single global setting.

Solution: a dedicated llama.cpp-scoped settings file loaded via `claude --settings <file>` (layers additively on top of `~/.claude/settings.json`), wired through a thin wrapper.

The wrapper:

- exports `ANTHROPIC_BASE_URL=http://${LLAMA_CPP_HOST:-127.0.0.1}:${LLAMA_CPP_PORT:-8080}`.
- sets `ANTHROPIC_API_KEY=$LLAMA_CPP_API_KEY`.
- defaults the key to `sk-no-key-required` because llama.cpp accepts unauthenticated local requests unless started with `--api-key`.
- invokes `claude --settings ~/.claude/settings.llama-cpp.json "$@"`.

Pass `--model` / `-m nemotron-3.5` to pick the model.

The wrapper injects its default `--model $CLAUDE_LLAMA_CPP_MODEL` only when you did not pass one, so there is no duplicate flag.

| Variable                    | Default                                 | Purpose                                                             |
| --------------------------- | --------------------------------------- | ------------------------------------------------------------------- |
| `LLAMA_CPP_HOST`            | `127.0.0.1`                             | Same as `,llama-cpp`                                                |
| `LLAMA_CPP_PORT`            | `8080`                                  | Same as `,llama-cpp`                                                |
| `LLAMA_CPP_API_KEY`         | `sk-no-key-required`                    | Sent as `ANTHROPIC_API_KEY` (Claude Code uses this for bearer auth) |
| `CLAUDE_LLAMA_CPP_MODEL`    | `nemotron-3.5`                          | Default model; overridden by a caller `--model`/`-m`, empty to skip |
| `CLAUDE_LLAMA_CPP_SETTINGS` | `$HOME/.claude/settings.llama-cpp.json` | Point at an alternate llama.cpp settings file                       |

`autoCompactWindow=200000` leaves a ~62k token buffer under the 262144-token server context for the next turn's prompt, tool outputs, and model reply.

`env.CLAUDE_CODE_ATTRIBUTION_HEADER=0` stops Claude Code from prepending a per-request `x-anthropic-billing-header` that would miss the llama.cpp KV cache. Claude Code 2.1.220 copies `--settings` `env` into `process.env` and treats `"0"` as off.

```bash
,claude-llama-cpp                           # interactive session, default model nemotron-3.5
,claude-llama-cpp --model qwen3.5-9b        # Unsloth Qwen3.5 9B
,claude-llama-cpp -p "summarize README.md"  # one-shot prompt
```

Cloud Claude sessions are unaffected — plain `claude ...` still reads only `~/.claude/settings.json`, where `autoCompactWindow` stays unset so the default for `opus[1m]` applies.

## Sources and verification

- [`home/exact_bin/executable_,codex`](../../../../home/exact_bin/executable_,codex) → `~/bin/,codex`
- [`home/exact_lib/exact_,codex/main.py`](../../../../home/exact_lib/exact_,codex/main.py) → `~/lib/,codex/main.py`
- [`home/dot_codex/readonly_llama-cpp-model-catalog.json`](../../../../home/dot_codex/readonly_llama-cpp-model-catalog.json) → `~/.codex/llama-cpp-model-catalog.json` (defines the local llama.cpp router ids)
- [`home/exact_bin/executable_,codex-llama-cpp`](../../../../home/exact_bin/executable_,codex-llama-cpp) → `~/bin/,codex-llama-cpp`
- [`home/exact_bin/executable_,cursor-llama-cpp`](../../../../home/exact_bin/executable_,cursor-llama-cpp) → `~/bin/,cursor-llama-cpp`
- [`home/exact_lib/exact_,cursor-agent-local/install.sh`](../../../../home/exact_lib/exact_,cursor-agent-local/install.sh) → version-matched local-provider Cursor binary
- [`home/dot_config/opencode/readonly_opencode.personal.jsonc`](../../../../home/dot_config/opencode/readonly_opencode.personal.jsonc) / [`readonly_opencode.work.jsonc`](../../../../home/dot_config/opencode/readonly_opencode.work.jsonc) — declare the `llama-cpp` provider
- [`home/exact_bin/executable_,opencode-llama-cpp`](../../../../home/exact_bin/executable_,opencode-llama-cpp) → `~/bin/,opencode-llama-cpp`
- [`home/dot_claude/settings.llama-cpp.json`](../../../../home/dot_claude/settings.llama-cpp.json) → `~/.claude/settings.llama-cpp.json` (`autoCompactWindow: 200000` and `CLAUDE_CODE_ATTRIBUTION_HEADER=0`)
- [`home/exact_bin/executable_,claude-llama-cpp`](../../../../home/exact_bin/executable_,claude-llama-cpp) → `~/bin/,claude-llama-cpp`
