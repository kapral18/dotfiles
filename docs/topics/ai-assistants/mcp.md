---
sidebar_position: 8
---

# MCP Servers

A single canonical registry defines every MCP server once. At `chezmoi apply` time, generators render per-tool configs for Cursor, Claude Code, Gemini, Pi, Codex, OpenCode, and GitHub Copilot CLI, avoiding seven hand-maintained copies of the same server list.

Use this page when adding, removing, or debugging an MCP server, or when tracing how a server reaches a given assistant.

## Mental model

| Piece                                                                               | Role                                                                                      |
| ----------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| [`home/.chezmoidata/mcp_servers.yaml`](../../../home/.chezmoidata/mcp_servers.yaml) | Source of truth for server declarations                                                   |
| [`scripts/mcp_registry.py`](../../../scripts/mcp_registry.py)                       | Normalizes registry entries and resolves `$(command)` strings through a login shell       |
| [`scripts/generate_mcp_configs.py`](../../../scripts/generate_mcp_configs.py)       | Emits tool-specific `{ "mcpServers": { ... } }` documents                                 |
| Tool injectors                                                                      | Preserve live runtime-owned config while replacing only the MCP section                   |
| [`,mcp-token` bridge](../workflow/custom-commands/catalog.md)                       | Inject a fresh bearer per request when a tool cannot perform the hosted OAuth flow itself |

The registry mechanics are generic. The currently declared server set is work-profile-only and Elastic-domain-specific.

## Registry: `mcp_servers.yaml`

Each entry is one of two shapes:

| Shape          | Required fields                               | Optional fields                                                                                                                          |
| -------------- | --------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| Command server | `name`, `work_only`, `command`, `args` (list) | `exclude_tools` (a list of tool names) to omit the server for specific tools that cannot express per-tool membership via `oauth_by_tool` |
| HTTP server    | `name`, `work_only`, `type: http`, `url`      | `oauth_by_tool` for per-tool OAuth client metadata, since tools expect different OAuth field shapes                                      |

`work_only: true` servers are emitted only when the `isWork` chezmoi variable is set. The personal profile currently emits no declared MCP servers.

The work set includes `scsi-main`, `scsi-local`, and `slack`:

| Server       | Current behavior                                                                                                                                                                                |
| ------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `scsi-main`  | Hosted Semantic Code Search server using Elastic SSO/OAuth. Cursor, Claude, Gemini, and Pi each have tool-specific OAuth metadata because they expect different field shapes and redirect URIs. |
| `scsi-local` | Local SCSI stdio backend emitted to every work-profile harness, including Copilot and Codex.                                                                                                    |
| `slack`      | Slack MCP server with per-tool OAuth metadata.                                                                                                                                                  |

Copilot and Codex get `scsi-local` as a stdio server and `scsi-main` plus `slack` as local `,mcp-token --bridge` stdio servers that forward to the hosted endpoints with per-request bearer injection. OpenCode gets `scsi-local` only: its injector intentionally emits command servers and skips every HTTP entry.

### Hosted OAuth exceptions

Copilot cannot run the hosted servers' OAuth flows itself. It hardcodes its OAuth redirect to `http://127.0.0.1:{port}/`, which is not registered for the SCSI Okta app or the public Slack client.

Slack's MCP authorization server offers no dynamic client registration and requires a client secret at the token endpoint: `grant_types = [authorization_code, refresh_token]`, `token_endpoint_auth_methods = [client_secret_post]`.

Both `scsi-main` and `slack` therefore give their `copilot` block a `tokenBridge` value naming the `,mcp-token` token source. Copilot rides the rotating token cursor-cli already minted rather than running OAuth itself, and the bridge re-reads that cache per request, so a session never depends on a token captured at launch.

Codex supports streamable HTTP MCP natively, but its OAuth callback settings are global: `mcp_oauth_callback_port` / `mcp_oauth_callback_url`. The hosted SCSI and Slack apps need different approved callback registrations, and its `bearer_token_env_var` support reads the env var once at launch, dying with that token.

Both `scsi-main` and `slack` therefore give their `codex` block the same `tokenBridge` value, so Codex spawns the identical per-request stdio bridge.

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
python3 -m json.tool < ~/.cursor/mcp.json
python3 -c "import json; print(list(json.load(open('$HOME/.claude.json')).get('mcpServers', {})))"
codex mcp list     # bridge servers appear as local command servers
copilot mcp list   # lists the loaded Copilot servers and their transport types
```

### Refresh a hosted token by hand

To refresh manually, run:

```bash
,mcp-token <server> --login
```

Add `--quiet` when you do not want cursor-agent auth output in the terminal.

You normally do not run this by hand. The `,mcp-token --bridge` stdio servers rotate behind the seam whenever a request finds the current token short, missing, or rejected.

## Generation pipeline

The common pipeline has two stages:

| Stage                   | Script                                                                        | Purpose                                                   |
| ----------------------- | ----------------------------------------------------------------------------- | --------------------------------------------------------- |
| Normalize registry      | [`scripts/mcp_registry.py`](../../../scripts/mcp_registry.py)                 | Resolve `$(command)` strings through a login shell        |
| Generate per-tool shape | [`scripts/generate_mcp_configs.py`](../../../scripts/generate_mcp_configs.py) | Emit a tool-specific `{ "mcpServers": { ... } }` document |

Per-tool transforms handle schema differences, such as Cursor's `auth.CLIENT_ID` vs the standard `oauth` shape.

Pi gets one extra block:

```json
{ "settings": { "autoAuth": true } }
```

That lets `pi-mcp-adapter` run OAuth + reconnect automatically on the first tool call to a `needs-auth` server. It still opens the browser in an interactive session; it is not headless auth. Other tools have their own config schemas and do not get this block.

Tools whose config is not plain JSON get dedicated injectors with explicit ownership rules:

| Injector                                                                                          | Ownership rule                                                                                                                                                                                                                                            |
| ------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`scripts/inject_mcp_into_codex_toml.py`](../../../scripts/inject_mcp_into_codex_toml.py)         | Replaces a `# __MCP_SERVERS__` marker in the authoritative profile base, then reattaches only valid runtime MCP approvals, hook trust hashes, project trust levels, and unsigned-32-bit TUI model-availability counters. Other live tables are discarded. |
| [`scripts/inject_mcp_into_opencode_jsonc.py`](../../../scripts/inject_mcp_into_opencode_jsonc.py) | Replaces a `"mcp": "__MCP_SERVERS__"` placeholder with local command servers; HTTP entries are intentionally skipped.                                                                                                                                     |
| [`scripts/merge_claude_mcp.py`](../../../scripts/merge_claude_mcp.py)                             | Surgically updates only the `mcpServers` key in `~/.claude.json`, which Claude Code also writes runtime state into.                                                                                                                                       |

## Per-tool targets

| Tool        | Target file (`mcpServers`)          | Rendered by hook                                                                                                                           |
| ----------- | ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| Cursor      | `~/.cursor/mcp.json`                | [`run_onchange_after_07-generate-mcp-configs.sh.tmpl`](../../../home/.chezmoiscripts/run_onchange_after_07-generate-mcp-configs.sh.tmpl)   |
| Claude Code | `~/.claude.json` (`mcpServers` key) | [`run_onchange_after_07-generate-mcp-configs.sh.tmpl`](../../../home/.chezmoiscripts/run_onchange_after_07-generate-mcp-configs.sh.tmpl)   |
| Pi          | `~/.pi/agent/mcp.json`              | [`run_onchange_after_07-generate-mcp-configs.sh.tmpl`](../../../home/.chezmoiscripts/run_onchange_after_07-generate-mcp-configs.sh.tmpl)   |
| Gemini      | `~/.gemini/settings.json`           | [`run_onchange_after_07-merge-gemini-settings.sh.tmpl`](../../../home/.chezmoiscripts/run_onchange_after_07-merge-gemini-settings.sh.tmpl) |
| OpenCode    | `~/.config/opencode/opencode.jsonc` | [`run_onchange_after_07-merge-opencode-config.sh.tmpl`](../../../home/.chezmoiscripts/run_onchange_after_07-merge-opencode-config.sh.tmpl) |
| Codex       | `~/.codex/config.toml`              | [`run_onchange_after_07-merge-codex-config.sh.tmpl`](../../../home/.chezmoiscripts/run_onchange_after_07-merge-codex-config.sh.tmpl)       |
| Copilot     | `~/.copilot/mcp-config.json`        | [`run_onchange_after_07-merge-copilot-config.sh.tmpl`](../../../home/.chezmoiscripts/run_onchange_after_07-merge-copilot-config.sh.tmpl)   |

## Copilot transform and launch wiring

Copilot transform behavior:

| Server class      | Emitted shape                                                                                           |
| ----------------- | ------------------------------------------------------------------------------------------------------- |
| stdio             | `type: "local"` with `tools: ["*"]`                                                                     |
| OAuth HTTP        | `type: "http"` with `oauthClientId`, `auth.redirectPort`, and `oauthScopes`                             |
| Token-bridge HTTP | `type: "local"` running `,mcp-token <source> --bridge --url <url>` when the block carries `tokenBridge` |

Copilot's wired servers:

- `slack` and `scsi-main` are emitted as token-bridge stdio servers.
- Each `copilot` block sets `tokenBridge: "<source>"`; the generator emits the bridge command with the server's registry URL, so no Authorization value or placeholder is ever baked into the config.
- `scsi-local` is emitted as a stdio server (`type: "local"`). It has no OAuth because it runs locally with `pass` Elasticsearch credentials, so no token is needed.

The built-in `github-mcp-server` is provided by Copilot and is not emitted.

### Per-request token bridge

[`,mcp-token`](../workflow/custom-commands/catalog.md) `--bridge --url <endpoint>` speaks stdio MCP to the agent and forwards each message as an HTTP POST to the hosted endpoint with a freshly selected bearer. Copilot and Codex spawn it like any local MCP server, so their sessions no longer depend on any single token's lifetime.

Per request, the bridge reads the freshest still-valid token from cursor-cli's per-project OAuth caches at `~/.cursor/projects/*/mcp-auth.json`. Cursor runs the `authorization_code` flow with its own approved clients (Slack workspace app / SCSI Elastic Okta) and refreshes the rotating token in place.

| Bridge event                                         | Behavior                                                                                                                                                      |
| ---------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Token missing or below `BLOCKING_ROTATE_TTL_SECONDS` | Rotate synchronously through cursor's refresh grant before sending; repeated rotation failures are throttled.                                                 |
| `401` / `403` mid-session                            | Re-acquire (rotating), retry once, and only when the retry would use a different token.                                                                       |
| `404` after a session was established                | Re-play the cached `initialize` handshake (new `Mcp-Session-Id`, response suppressed) and retry, so server-side session expiry never kills the agent session. |
| SSE response                                         | Every `data:` event streams through in order (progress notifications before the response).                                                                    |
| stdin EOF                                            | Best-effort `DELETE` of the server session, then exit.                                                                                                        |

SCSI tokens are JWTs, so `,mcp-token` uses their `exp`. Direct `--login` still guarantees runway.

### Rotation rules

`--login` rotates silently below `MIN_TTL_SECONDS`; `--login --no-proactive-rotation` (used by `,cursor`, whose runtime refreshes tokens itself) keeps that proactive rotation off the critical path while the final `BLOCKING_ROTATE_TTL_SECONDS` window, expired tokens, and revoked tokens still rotate synchronously.

The Cursor mode checks the current working workspace's own `mcp-auth.json` before the session starts. It resolves Cursor's project directory from matching `.workspace-trusted` metadata, with Cursor's deterministic path slug as the fallback. Missing access tokens and stale JWTs without a refresh chain run `cursor-agent mcp login <server>` in that working directory; an existing refresh chain remains runtime-owned. This prevents a valid token in another project cache from masking an unauthenticated current workspace without adding a live MCP handshake to every launch.

Silent rotation relies on cursor running the provider's `refresh_token` grant whenever a stored access token stops working. `,mcp-token` invalidates the access token in the newest project cache that holds a `refresh_token` and whose `.workspace-trusted` records an existing workspace directory, runs a bounded `cursor-agent mcp list-tools <server>` in that workspace, and cursor writes the freshly minted chain back in place with no browser and without revoking the in-flight token running sessions already hold.

Concurrent rotations serialize through `~/.cache/mcp-token/rotation.lock` and recheck whether rotation remains due before touching the shared cache.

### Opaque token liveness

Opaque tokens such as Slack expose no expiry. The local refresh ledger under `~/.cache/mcp-token/` can pin a token the provider has since revoked, so ledger state and cache mtime alone do not prove an opaque token is live.

`--login` validates the ledger-selected opaque token with a minimal MCP `initialize` probe against the server's URL from the generated `~/.cursor/mcp.json`:

| Probe result                                    | Behavior                                                                                                                                                       |
| ----------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `2xx`                                           | Keep the token.                                                                                                                                                |
| `401` / `403`                                   | Treat it as revoked, try a synchronous silent rotation first, then probe other cached opaque tokens newest-cache first and adopt a live one without a browser. |
| No live candidate                               | Run the cursor browser flow.                                                                                                                                   |
| Network errors, timeouts, `5xx`, or missing URL | Leave liveness unknown and preserve the existing ledger token rather than forcing a browser login.                                                             |

Plain reads stay local and never probe.

### Copilot config safety

The rendered `~/.copilot/mcp-config.json` carries no secrets — bridge entries name only the command, token source, and URL — and rendering happens entirely at `chezmoi apply` time. `,copilot` is a thin exec of the real binary; all `,copilot-*` provider wrappers route through it.

The config is still written `0600` and `~/.copilot/` is forced to `0700`.

## Codex bridge wiring

Codex's wired servers:

- `slack` and `scsi-main` are emitted by [`scripts/inject_mcp_into_codex_toml.py`](../../../scripts/inject_mcp_into_codex_toml.py) as `,mcp-token --bridge` command servers. No bearer value or env-var contract is written to `~/.codex/config.toml`.
- `,codex` performs no token work at launch; the bridge owns auth per request. The wrapper only injects local llama.cpp model catalog metadata when a local model is selected.
- `scsi-local` is emitted as a normal stdio server in `~/.codex/config.toml`.

LetsFG is intentionally not exposed through the shared MCP registry because its tools are irrelevant to most sessions. Agents load its skill on demand instead. See [Tool configs](tool-configs/index.md) for details.

## Related

- [Tool configs](tool-configs/index.md) — per-assistant settings and profile merging
- [Model registry & routing](model-registry.md) — the parallel registry for model definitions
- [The Agentic Operating System](index.md) — governance layer
