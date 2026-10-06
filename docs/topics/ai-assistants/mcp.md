---
sidebar_position: 8
---

# MCP Servers

A single canonical registry defines every MCP server once. At `chezmoi apply` time, generators render per-tool configs for Claude Code, Antigravity, Pi, OMP, Codex, and OpenCode, avoiding six hand-maintained copies of the same server list.

Use this page when adding, removing, or debugging an MCP server, or when tracing how a server reaches a given assistant.

## Mental model

| Piece                                                                               | Role                                                                                |
| ----------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| [`home/.chezmoidata/mcp_servers.yaml`](../../../home/.chezmoidata/mcp_servers.yaml) | Source of truth for server declarations                                             |
| [`scripts/mcp_registry.py`](../../../scripts/mcp_registry.py)                       | Normalizes registry entries and resolves `$(command)` strings through a login shell |
| [`scripts/generate_mcp_configs.py`](../../../scripts/generate_mcp_configs.py)       | Emits tool-specific `{ "mcpServers": { ... } }` documents                           |
| Tool injectors                                                                      | Preserve live runtime-owned config while replacing only the MCP section             |

The registry mechanics are generic. The currently declared server set is work-profile-only.

## Registry: `mcp_servers.yaml`

Each entry is one of two shapes:

| Shape          | Required fields                               | Optional fields                                                                                                                          |
| -------------- | --------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| Command server | `name`, `work_only`, `command`, `args` (list) | `exclude_tools` (a list of tool names) to omit the server for specific tools that cannot express per-tool membership via `oauth_by_tool` |
| HTTP server    | `name`, `work_only`, `type: http`, `url`      | `oauth_by_tool` for per-tool OAuth client metadata, since tools expect different OAuth field shapes                                      |

`work_only: true` servers are emitted only when the `isWork` chezmoi variable is set. The personal profile currently emits no declared MCP servers.

The work set declares one server:

| Server  | Current behavior                                                                              |
| ------- | --------------------------------------------------------------------------------------------- |
| `slack` | Hosted Slack MCP server. Claude Code and Pi carry OAuth client metadata, so only they get it. |

An HTTP server reaches a harness only when `oauth_by_tool` names that harness; every other harness omits it. OpenCode and Codex emit command servers only and skip every HTTP entry.

### Hosted OAuth limits

Slack's MCP authorization server offers no dynamic client registration and requires a client secret at the token endpoint: `grant_types = [authorization_code, refresh_token]`, `token_endpoint_auth_methods = [client_secret_post]`.

Codex supports streamable HTTP MCP natively, but its OAuth callback settings are global (`mcp_oauth_callback_port` / `mcp_oauth_callback_url`), and its `bearer_token_env_var` support reads the env var once at launch, dying with that token. Codex therefore gets no hosted server.

Pi 1.0.0 connects HTTP servers through its built-in MCP support, which accepts a registered OAuth client (`oauth.clientId`, `callbackPort` or `callbackUrl`, `scope`). The Pi `slack` row reuses Slack's public MCP client (`1601185624273.8899143856786`), spells the loopback URI like Claude's (`http://localhost:3118/callback`), and requests the six granular `search:read.*` scopes from `scopes_supported` in `https://mcp.slack.com/.well-known/oauth-authorization-server`. Pi parses the row and reports `needs sign-in`; whether Slack's consent and token exchange succeed (the token endpoint lists only `client_secret_post`) is unverified until `pi mcp login slack` runs on the work profile.

## Using it

### Add or change a server

1. Edit [`home/.chezmoidata/mcp_servers.yaml`](../../../home/.chezmoidata/mcp_servers.yaml) and set `work_only` appropriately.
2. Preview the rendered per-tool configs:

   ```bash
   chezmoi diff
   ```

3. Regenerate them:

   ```bash
   chezmoi apply
   ```

Verification:

```bash
chezmoi apply
python3 -m json.tool < ~/.pi/agent/mcp.json
python3 -c "import json; print(list(json.load(open('$HOME/.claude.json')).get('mcpServers', {})))"
codex mcp list     # command servers only
```

## Generation pipeline

The common pipeline has two stages:

| Stage                   | Script                                                                        | Purpose                                                   |
| ----------------------- | ----------------------------------------------------------------------------- | --------------------------------------------------------- |
| Normalize registry      | [`scripts/mcp_registry.py`](../../../scripts/mcp_registry.py)                 | Resolve `$(command)` strings through a login shell        |
| Generate per-tool shape | [`scripts/generate_mcp_configs.py`](../../../scripts/generate_mcp_configs.py) | Emit a tool-specific `{ "mcpServers": { ... } }` document |

Per-tool transforms handle schema differences, such as Antigravity's `serverUrl` vs the standard `url` field.

Pi emits `{ url, oauth }` for HTTP servers, with `scope` normalised to space-separated tokens, as its built-in MCP expects. Other tools have their own config schemas.

Pi's built-in MCP defaults a server's `exposure` to `codemode`: its tools are not declared to the model and are called from `codemode` scripts as `tools.mcp__<server>__<tool>`. The registry sets no `exposure`, so Pi's `slack` row follows that default, while Claude Code declares the tools directly. See [Pi coding agent settings](tool-configs/pi.md#settings).

Tools whose config is not plain JSON get dedicated injectors with explicit ownership rules:

| Injector                                                                                          | Ownership rule                                                                                                                                                                                                                                            |
| ------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`scripts/inject_mcp_into_codex_toml.py`](../../../scripts/inject_mcp_into_codex_toml.py)         | Replaces a `# __MCP_SERVERS__` marker in the authoritative profile base, then reattaches only valid runtime MCP approvals, hook trust hashes, project trust levels, and unsigned-32-bit TUI model-availability counters. Other live tables are discarded. |
| [`scripts/inject_mcp_into_opencode_jsonc.py`](../../../scripts/inject_mcp_into_opencode_jsonc.py) | Replaces a `"mcp": "__MCP_SERVERS__"` placeholder with local command servers; HTTP entries are intentionally skipped.                                                                                                                                     |
| [`scripts/merge_claude_mcp.py`](../../../scripts/merge_claude_mcp.py)                             | Surgically updates only the `mcpServers` key in `~/.claude.json`, which Claude Code also writes runtime state into.                                                                                                                                       |

## Per-tool targets

| Tool        | Target file (`mcpServers`)          | Rendered by hook                                                                                                                           |
| ----------- | ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| Claude Code | `~/.claude.json` (`mcpServers` key) | [`run_onchange_after_07-generate-mcp-configs.sh.tmpl`](../../../home/.chezmoiscripts/run_onchange_after_07-generate-mcp-configs.sh.tmpl)   |
| Pi          | `~/.pi/agent/mcp.json`              | [`run_onchange_after_07-generate-mcp-configs.sh.tmpl`](../../../home/.chezmoiscripts/run_onchange_after_07-generate-mcp-configs.sh.tmpl)   |
| OMP         | `~/.omp/agent/mcp.json`             | [`run_onchange_after_07-generate-mcp-configs.sh.tmpl`](../../../home/.chezmoiscripts/run_onchange_after_07-generate-mcp-configs.sh.tmpl)   |
| Antigravity | `~/.gemini/config/mcp_config.json`  | [`run_onchange_after_07-generate-mcp-configs.sh.tmpl`](../../../home/.chezmoiscripts/run_onchange_after_07-generate-mcp-configs.sh.tmpl)   |
| OpenCode    | `~/.config/opencode/opencode.jsonc` | [`run_onchange_after_07-merge-opencode-config.sh.tmpl`](../../../home/.chezmoiscripts/run_onchange_after_07-merge-opencode-config.sh.tmpl) |
| Codex       | `~/.codex/config.toml`              | [`run_onchange_after_07-merge-codex-config.sh.tmpl`](../../../home/.chezmoiscripts/run_onchange_after_07-merge-codex-config.sh.tmpl)       |

LetsFG is intentionally not exposed through the shared MCP registry because its tools are irrelevant to most sessions. Agents load its skill on demand instead. See [Tool configs](tool-configs/index.md) for details.

## Related

- [Tool configs](tool-configs/index.md) — per-assistant settings and profile merging
- [The Agentic Operating System](index.md) — governance layer
