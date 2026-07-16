---
sidebar_position: 8
---

# MCP Servers

A single canonical registry defines every MCP server once.

At `chezmoi apply` time, generators render per-tool configs for:

- Cursor
- Claude Code
- Gemini
- Pi
- Codex
- OpenCode
- GitHub Copilot CLI

That avoids hand-maintaining the same server list in seven config formats.

Use when adding, removing, or debugging an MCP server, or understanding how a server reaches a given assistant.

## Registry: `mcp_servers.yaml`

Source of truth: [`home/.chezmoidata/mcp_servers.yaml`](../../../home/.chezmoidata/mcp_servers.yaml).

Each entry is one of two shapes:

- **Command server** — `name`, `work_only`, `command`, `args` (list). A command server may also carry `exclude_tools` (a list of tool names) to omit it for specific tools that cannot express per-tool membership via `oauth_by_tool`.
- **HTTP server** — `name`, `work_only`, `type: http`, `url`, and optionally `oauth_by_tool` (per-tool OAuth client metadata, since tools expect different OAuth field shapes).

The registry mechanics are generic. The currently declared server set is work-profile-only and Elastic-domain-specific:

- `scsi-main` is the hosted Semantic Code Search server using Elastic SSO/OAuth. Cursor, Claude, Gemini, and Pi each have tool-specific OAuth metadata because they expect different field shapes and redirect URIs.
- `scsi-local` is the local SCSI stdio backend and is excluded from Copilot once the hosted server is omitted there.
- `slack` is the Slack MCP server with per-tool OAuth metadata.
- Copilot cannot run the hosted servers' OAuth flows itself: it hardcodes its OAuth redirect to `http://127.0.0.1:{port}/`, which is not registered for the SCSI Okta app or the public Slack client, and Slack's MCP authorization server offers no dynamic client registration and requires a client secret at the token endpoint (`grant_types = [authorization_code, refresh_token]`, `token_endpoint_auth_methods = [client_secret_post]`). Both `scsi-main` and `slack` therefore give their `copilot` block a `headerAuth` value — a pre-resolved `Authorization: Bearer <token>` — so Copilot rides the rotating token cursor-cli already minted rather than running OAuth (see the Copilot transform below).
- Codex supports streamable HTTP MCP natively, but its OAuth callback settings are global (`mcp_oauth_callback_port` / `mcp_oauth_callback_url`) while the hosted SCSI and Slack apps need different approved callback registrations. Both `scsi-main` and `slack` therefore give their `codex` block a `bearerTokenEnvVar`; Codex's config names only the env var, and `,codex` fills it with the raw token from `,mcp-token` before launch.

`work_only: true` servers are emitted only when the `isWork` chezmoi variable is set. The personal profile currently emits no declared MCP servers. The work set includes `scsi-main`, `scsi-local`, and `slack`; Copilot gets `scsi-local` as a stdio server and `scsi-main` plus `slack` via bearer headers, while Codex gets all three with hosted servers backed by bearer-token env vars.

## Generation pipeline

The generation pipeline has two common stages:

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

- [`scripts/inject_mcp_into_codex_toml.py`](../../../scripts/inject_mcp_into_codex_toml.py) — replaces a `# __MCP_SERVERS__` marker in the authoritative profile base, then reattaches only valid runtime MCP approvals, hook trust hashes, project trust levels, and unsigned-32-bit TUI model-availability counters. Other live tables are discarded.
- [`scripts/inject_mcp_into_opencode_jsonc.py`](../../../scripts/inject_mcp_into_opencode_jsonc.py) — replaces a `"mcp": "__MCP_SERVERS__"` placeholder in the OpenCode JSONC.
- [`scripts/merge_claude_mcp.py`](../../../scripts/merge_claude_mcp.py) — surgically updates only the `mcpServers` key in `~/.claude.json`, which Claude Code also writes runtime state into.

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

Copilot transform behavior:

| Server class     | Emitted shape                                                                                             |
| ---------------- | --------------------------------------------------------------------------------------------------------- |
| stdio            | `type: "local"` with `tools: ["*"]`                                                                       |
| OAuth HTTP       | `type: "http"` with `oauthClientId`, `auth.redirectPort`, and `oauthScopes`                               |
| Header-auth HTTP | `type: "http"` with `headers.Authorization` (when the block carries `headerAuth`; OAuth keys are skipped) |

Copilot's wired servers:

- `slack` and `scsi-main` are emitted as header-auth HTTP servers. Each `copilot` block sets `headerAuth: "$(,mcp-token <server> --bearer)"`, which the generator resolves into `headers.Authorization` when a fresh token exists. If the local cursor-cli cache is stale during `chezmoi apply`, the generator emits a refresh placeholder instead of failing the apply; [`,copilot`](../workflow/custom-commands/catalog.md) asks the generator for a typed plan from the canonical registry, deduplicates token sources, runs `,mcp-token <source> --login --quiet --launch-json` once per source, and passes those in-memory headers into one render immediately before launch. If no valid token is returned, config render fails, or a placeholder remains, `,copilot` stops before launching so Copilot never starts with a known-bad bearer header. [`,mcp-token`](../workflow/custom-commands/catalog.md) reads the freshest still-valid token for that server from cursor-cli's per-project OAuth caches (`~/.cursor/projects/*/mcp-auth.json`); cursor runs the `authorization_code` flow with its own approved clients (Slack workspace app / SCSI Elastic Okta) and refreshes the rotating token in place. SCSI tokens are JWTs, so `,mcp-token` uses their `exp`. Direct `--login` still guarantees runway. Managed launchers use `--launch-json` to capture a still-valid token short of `MIN_TTL_SECONDS` immediately, then start detached `--rotate` after the fixed header or env value is ready. The final `BLOCKING_ROTATE_TTL_SECONDS` window, expired tokens, and revoked tokens still rotate synchronously. Silent rotation exploits the fact that cursor runs the provider's `refresh_token` grant whenever a stored access token stops working — `,mcp-token` invalidates the access token in the newest project cache that holds a `refresh_token` and whose `.workspace-trusted` records an existing workspace directory, runs a bounded `cursor-agent mcp list-tools <server>` in that workspace, and cursor writes the freshly minted chain back in place with no browser and without revoking the in-flight token running sessions already hold. Concurrent deferred workers serialize through `~/.cache/mcp-token/rotation.lock` and recheck whether rotation remains due before touching the shared cache. Opaque tokens such as Slack expose no expiry and the local refresh ledger under `~/.cache/mcp-token/` can pin a token the provider has since revoked, so ledger state and cache mtime alone do not prove an opaque token is live. Launch capture therefore validates the ledger-selected opaque token with a minimal MCP `initialize` probe against the server's URL from the generated `~/.cursor/mcp.json`: a `2xx` keeps it, a `401`/`403` means it is revoked so a synchronous silent rotation is tried first, then other cached opaque tokens are probed newest-cache first and a live one is adopted without a browser, and only when no live candidate exists does the cursor browser flow run. Network errors, timeouts, `5xx`, or a missing URL leave liveness unknown and preserve the existing ledger token rather than forcing a browser login. Plain reads stay local and never probe. To refresh manually, run `,mcp-token <server> --login`; add `--quiet` when you do not want cursor-agent auth output in the terminal. You normally do not run this by hand: launch Copilot via [`,copilot`](../workflow/custom-commands/catalog.md), which holds a private lock across the batch, validates every rendered Authorization value and rejects placeholders, atomically replaces `mcp-config.json` only when its parsed JSON changes, starts due proactive rotations, updates only the `copilot-mcp` generated-artifact row after a semantic change, and then execs `copilot` with the original arguments. The token-bearing `~/.copilot/mcp-config.json` is written `0600` and `~/.copilot/` is forced to `0700`. All `,copilot-*` provider wrappers route through `,copilot`. This keeps token refresh out of `chezmoi apply`, which only deploys the static config.
- `scsi-local` is emitted as a stdio server (`type: "local"`); it has no OAuth (it runs locally with `pass` Elasticsearch credentials), so no token is needed.

The built-in `github-mcp-server` is provided by Copilot and is not emitted.

Codex's wired servers:

- `slack` and `scsi-main` are emitted by [`scripts/inject_mcp_into_codex_toml.py`](../../../scripts/inject_mcp_into_codex_toml.py) as streamable HTTP TOML blocks with `url` and `bearer_token_env_var`. No bearer value is written to `~/.codex/config.toml`.
- `,codex` reads those env-var declarations from `~/.codex/config.toml`, runs `,mcp-token <server> --login --quiet --launch-json` for each configured hosted server, exports the captured raw token into the configured env var, starts due proactive rotations after capture, and then execs the real Codex binary. If no valid token is returned, it exits before launch so Codex does not start with known-missing MCP auth.
- `scsi-local` is emitted as a normal stdio server in `~/.codex/config.toml`.

LetsFG is intentionally not exposed through the shared MCP registry because its tools are irrelevant to most sessions; agents load its skill on demand instead. See [Tool configs](tool-configs/index.md) for details.

## Add or change a server

1. Edit [`home/.chezmoidata/mcp_servers.yaml`](../../../home/.chezmoidata/mcp_servers.yaml) (set `work_only` appropriately).
2. `chezmoi diff` to preview the rendered per-tool configs.
3. `chezmoi apply` to regenerate them.

Verification:

```bash
chezmoi apply
python3 -m json.tool < ~/.cursor/mcp.json
python3 -c "import json; print(list(json.load(open('$HOME/.claude.json')).get('mcpServers', {})))"
codex mcp list     # via shell function -> ,codex, so bearer env vars are populated
copilot mcp list   # lists the loaded Copilot servers and their transport types
```

## Related

- [Tool configs](tool-configs/index.md) — per-assistant settings and profile merging
- [Model registry & routing](model-registry.md) — the parallel registry for model definitions
- [The Agentic Operating System](index.md) — governance layer
