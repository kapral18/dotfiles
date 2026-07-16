---
sidebar_position: 4
title: Launchers
---

# Launchers

These launchers make local llama.cpp models usable from Codex, OpenCode, and Claude Code without repeating provider flags every time. Each wrapper solves a different harness-specific problem: Codex needs local model metadata plus provider routing, OpenCode needs model ids qualified to its configured provider, and Claude Code needs a llama.cpp-scoped settings file.

## Mental model

Codex has two layers. The transparent `,codex` wrapper supplies catalog metadata for local ids (`local` and `local-max`), while `,codex-llama-cpp` supplies the provider routing flags that point Codex at `llama-server`.

OpenCode reads providers from `~/.config/opencode/opencode.jsonc`, so its launcher only normalizes model selection and passes the rest through.

Claude Code has one global `autoCompactWindow`, but cloud `opus[1m]` and local llama.cpp need different values. The llama.cpp launcher loads an additive settings file with `autoCompactWindow: 200000` and leaves plain cloud Claude sessions untouched.

## Using it

### Codex launcher metadata

Codex only has first-class model metadata for slugs present in its model catalog; unknown local slugs use fallback metadata and emit a warning. This repo ships a transparent `,codex` wrapper plus a small local catalog for the llama.cpp models.

The wrapper refreshes any configured Codex hosted-MCP bearer-token env vars, then injects `-c model_catalog_json="$HOME/.codex/llama-cpp-model-catalog.json"` when the selected model is one of the local llama.cpp ids (`local` or `local-max`), in either `--model <id>` or `--model=<id>` form.

Other Codex invocations execute `/opt/homebrew/bin/codex` directly after the MCP env-var setup.

### Codex launcher (`,codex-llama-cpp`)

The `,codex` shim above only supplies catalog metadata; Codex still needs the provider routing flags to reach llama-server. `,codex-llama-cpp` bakes those in so you don't type them every time.

The wrapper injects:

| Codex config key                     | Value                                           |
| ------------------------------------ | ----------------------------------------------- |
| `model_providers.llama-cpp.base_url` | `http://${LLAMA_CPP_HOST}:${LLAMA_CPP_PORT}/v1` |
| `model_providers.llama-cpp.name`     | `llama.cpp`                                     |
| `model_provider`                     | `llama-cpp`                                     |

The `~/bin/,codex` shim still injects catalog metadata. Pass `--model` / `-m local-max` to pick the model.

The wrapper adds its default `--model $CODEX_LLAMA_CPP_MODEL` only when you did not pass one, so there is no duplicate flag.

```bash
,codex-llama-cpp                          # default model local
,codex-llama-cpp --model local-max        # abliterated sibling
,codex-llama-cpp -m local-max exec "..."  # one-shot
```

### OpenCode launcher (`,opencode-llama-cpp`)

OpenCode reads providers from `~/.config/opencode/opencode.jsonc`; there is no per-invocation provider override.

The `llama-cpp` provider is declared in both profile sources and flows through the merge hook unchanged:

| Field       | Value                      |
| ----------- | -------------------------- |
| Provider id | `llama-cpp`                |
| Base URL    | `http://127.0.0.1:8080/v1` |
| Models      | `local`, `local-max`       |

The provider id avoids a dot (`llama-cpp`, not `llama.cpp`) because OpenCode's SDK derives an incorrect lookup key from dotted ids.

Pass `--model`/`-m` with a bare id (`local`/`local-max`) — the wrapper qualifies it to `llama-cpp/<id>` — or the full `llama-cpp/<id>`. With no `--model`, it defaults to `llama-cpp/$OPENCODE_LLAMA_CPP_MODEL` (`local`).

Any subcommand/args pass through.

```bash
,opencode-llama-cpp                            # interactive TUI, default model local
,opencode-llama-cpp --model local-max          # abliterated sibling (bare id auto-qualified)
,opencode-llama-cpp --model local-max run "…"  # one-shot
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

Pass `--model` / `-m local-max` to pick the model.

The wrapper injects its default `--model $CLAUDE_LLAMA_CPP_MODEL` only when you did not pass one, so there is no duplicate flag.

| Variable                    | Default                                 | Purpose                                                             |
| --------------------------- | --------------------------------------- | ------------------------------------------------------------------- |
| `LLAMA_CPP_HOST`            | `127.0.0.1`                             | Same as `,llama-cpp`                                                |
| `LLAMA_CPP_PORT`            | `8080`                                  | Same as `,llama-cpp`                                                |
| `LLAMA_CPP_API_KEY`         | `sk-no-key-required`                    | Sent as `ANTHROPIC_API_KEY` (Claude Code uses this for bearer auth) |
| `CLAUDE_LLAMA_CPP_MODEL`    | `local`                                 | Default model; overridden by a caller `--model`/`-m`, empty to skip |
| `CLAUDE_LLAMA_CPP_SETTINGS` | `$HOME/.claude/settings.llama-cpp.json` | Point at an alternate llama.cpp settings file                       |

`autoCompactWindow=200000` leaves a ~62k token buffer under the 262144-token server context for the next turn's prompt, tool outputs, and model reply.

```bash
,claude-llama-cpp                           # interactive session, default model local
,claude-llama-cpp -p "summarize README.md"  # one-shot prompt
,claude-llama-cpp --model local-max         # use the abliterated sibling
```

Cloud Claude sessions are unaffected — plain `claude ...` still reads only `~/.claude/settings.json`, where `autoCompactWindow` stays unset so the default for `opus[1m]` applies.

## Sources and verification

- [`home/exact_bin/executable_,codex`](../../../../home/exact_bin/executable_,codex) → `~/bin/,codex`
- [`home/exact_lib/exact_,codex/main.py`](../../../../home/exact_lib/exact_,codex/main.py) → `~/lib/,codex/main.py`
- [`home/dot_codex/readonly_llama-cpp-model-catalog.json`](../../../../home/dot_codex/readonly_llama-cpp-model-catalog.json) → `~/.codex/llama-cpp-model-catalog.json` (defines both `local` and `local-max`)
- [`home/exact_bin/executable_,codex-llama-cpp`](../../../../home/exact_bin/executable_,codex-llama-cpp) → `~/bin/,codex-llama-cpp`
- [`home/dot_config/opencode/readonly_opencode.personal.jsonc`](../../../../home/dot_config/opencode/readonly_opencode.personal.jsonc) / [`readonly_opencode.work.jsonc`](../../../../home/dot_config/opencode/readonly_opencode.work.jsonc) — declare the `llama-cpp` provider
- [`home/exact_bin/executable_,opencode-llama-cpp`](../../../../home/exact_bin/executable_,opencode-llama-cpp) → `~/bin/,opencode-llama-cpp`
- [`home/dot_claude/settings.llama-cpp.json`](../../../../home/dot_claude/settings.llama-cpp.json) → `~/.claude/settings.llama-cpp.json` (contains only `autoCompactWindow: 200000`)
- [`home/exact_bin/executable_,claude-llama-cpp`](../../../../home/exact_bin/executable_,claude-llama-cpp) → `~/bin/,claude-llama-cpp`
