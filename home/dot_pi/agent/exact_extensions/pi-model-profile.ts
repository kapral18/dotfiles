// Managed by chezmoi (source: home/dot_pi/agent/exact_extensions/pi-model-profile.ts).
// `/model-profile` — switch this machine's whole Pi pricing without leaving the session.
//
// The command is a thin front end for `~/bin/,pi-model-profile`, which stays the only writer and
// the only validator of the state file. This extension never writes
// `${XDG_STATE_HOME:-$HOME/.local/state}/chezmoi/pi-model-profile` and never parses tiering.yaml:
// it reads names from `--list`, runs the picker, then reads the chosen session row back from
// `--session <name>`.
//
// The picker's `chezmoi apply` re-renders every ~/.pi/agent/agents/*.md profile and re-patches
// `defaultProvider`/`defaultModel`/`defaultThinkingLevel` in the installed settings.json, so new
// sessions and subagents pick the profile up on their own. The live session does not: pi resolved
// its model at session start. So after a successful apply this also calls setModel/setThinkingLevel
// with the profile's session row, which is session-scoped and does not touch the configured
// default the apply just wrote.

import type { ExtensionAPI, ExtensionCommandContext } from "@earendil-works/pi-coding-agent"
import type { AutocompleteItem } from "@earendil-works/pi-tui"

// pi's own ThinkingLevel union (pi-agent-core dist/types.d.ts). Spelled locally because
// @earendil-works/pi-agent-core is not in the pnpm global-links tree pi resolves extensions
// against; only pi-coding-agent and pi-tui are.
type ThinkingLevel = "off" | "minimal" | "low" | "medium" | "high" | "xhigh" | "max"

const PICKER = ",pi-model-profile"
// Read-only lookups are two `chezmoi data` runs at worst.
const READ_TIMEOUT_MS = 20_000
// The switch itself is a full `chezmoi apply` over 16 agent profiles plus the Pi merge hook.
const APPLY_TIMEOUT_MS = 600_000
const ACTIVE_MARKER = " (active)"
const STDERR_TAIL_CHARS = 400

const THINKING_LEVELS: ReadonlySet<string> = new Set<ThinkingLevel>([
  "off",
  "minimal",
  "low",
  "medium",
  "high",
  "xhigh",
  "max",
])

function parseNames(stdout: string): string[] {
  return stdout
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
}

// `--show`'s first line is `active pi model profile: <name>`; the rest are indented rows.
function parseActiveName(stdout: string): string {
  const first = stdout.split("\n", 1)[0] ?? ""
  const match = /^active pi model profile:\s*(\S+)\s*$/.exec(first.trim())
  return match ? match[1] : ""
}

// `--session <name>` prints `<provider>/<model-id>\t<effort>`. Provider splits at the FIRST slash:
// model ids carry slashes of their own (`openrouter/z-ai/glm-5.3`), the provider never does.
function parseSessionRow(stdout: string): { provider: string; modelId: string; level: ThinkingLevel } | null {
  const line = stdout.split("\n").find((candidate) => candidate.trim())
  if (!line) return null
  const [model = "", effort = ""] = line.split("\t")
  const slash = model.indexOf("/")
  if (slash <= 0 || slash === model.length - 1) return null
  const level = effort.trim()
  if (!THINKING_LEVELS.has(level)) return null
  return { provider: model.slice(0, slash), modelId: model.slice(slash + 1), level: level as ThinkingLevel }
}

function stderrTail(result: { stderr: string; stdout: string }): string {
  const text = (result.stderr.trim() || result.stdout.trim()).split("\n").filter(Boolean).slice(-2).join(" ")
  return text.slice(-STDERR_TAIL_CHARS) || `${PICKER} failed`
}

async function listNames(pi: ExtensionAPI): Promise<string[]> {
  const result = await pi.exec(PICKER, ["--list"], { timeout: READ_TIMEOUT_MS })
  if (result.killed || result.code !== 0) return []
  return parseNames(result.stdout)
}

async function activeName(pi: ExtensionAPI): Promise<string> {
  const result = await pi.exec(PICKER, ["--show"], { timeout: READ_TIMEOUT_MS })
  if (result.killed || result.code !== 0) return ""
  return parseActiveName(result.stdout)
}

// Re-point the live session at the profile's own session row. A failure here is a warning, never an
// error: the profile IS applied at this point, it just did not reach this already-running session.
async function applyToLiveSession(pi: ExtensionAPI, ctx: ExtensionCommandContext, name: string): Promise<void> {
  const notApplied = (why: string) =>
    ctx.ui.notify(
      `Profile '${name}' is applied for new sessions and subagents, but this session's model was not switched (${why}). Use /model to switch it by hand.`,
      "warning",
    )

  const result = await pi.exec(PICKER, ["--session", name], { timeout: READ_TIMEOUT_MS })
  if (result.killed || result.code !== 0) {
    notApplied(`could not read its session row: ${stderrTail(result)}`)
    return
  }
  const row = parseSessionRow(result.stdout)
  if (!row) {
    notApplied(`its session row was not parseable: ${result.stdout.trim().slice(0, STDERR_TAIL_CHARS)}`)
    return
  }
  const model = ctx.modelRegistry.find(row.provider, row.modelId)
  if (!model) {
    notApplied(`${row.provider}/${row.modelId} is not in this session's model catalogue`)
    return
  }
  if (!(await pi.setModel(model))) {
    notApplied(`no configured authentication for provider '${row.provider}'`)
    return
  }
  pi.setThinkingLevel(row.level)
  ctx.ui.notify(`Pi model profile '${name}' applied; this session now runs ${row.provider}/${row.modelId} (${row.level}).`, "info")
}

export default function (pi: ExtensionAPI) {
  pi.registerCommand("model-profile", {
    description: "Switch this machine's Pi model profile (runs ,pi-model-profile, then re-points this session)",
    getArgumentCompletions: async (prefix: string): Promise<AutocompleteItem[] | null> => {
      const items = (await listNames(pi))
        .filter((name) => name.startsWith(prefix))
        .map((name) => ({ value: name, label: name }))
      return items.length > 0 ? items : null
    },
    handler: async (args: string, ctx: ExtensionCommandContext) => {
      // Dialogs and notifications both need dialog-capable UI (TUI or RPC); print/JSON mode has
      // neither, and a silent whole-machine model switch is worse than no command at all.
      if (!ctx.hasUI) return

      let name = args.trim()
      if (!name) {
        const names = await listNames(pi)
        if (!names.length) {
          ctx.ui.notify(`Could not list Pi model profiles (${PICKER} --list returned nothing).`, "error")
          return
        }
        const current = await activeName(pi)
        const labels = names.map((candidate) => (candidate === current ? `${candidate}${ACTIVE_MARKER}` : candidate))
        const picked = await ctx.ui.select("Pi model profile", labels)
        if (picked === undefined) {
          ctx.ui.notify("No profile selected.", "info")
          return
        }
        name = picked.endsWith(ACTIVE_MARKER) ? picked.slice(0, -ACTIVE_MARKER.length) : picked
      }

      ctx.ui.notify(`Applying Pi model profile '${name}' (full chezmoi apply)…`, "info")
      const applied = await pi.exec(PICKER, [name], { timeout: APPLY_TIMEOUT_MS })
      if (applied.killed || applied.code !== 0) {
        ctx.ui.notify(`Pi model profile '${name}' is selected but the apply failed; re-run \`chezmoi apply\`: ${stderrTail(applied)}`, "error")
        return
      }
      await applyToLiveSession(pi, ctx, name)
    },
  })
}
