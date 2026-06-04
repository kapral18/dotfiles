// Managed by chezmoi (source: home/dot_pi/agent/extensions/ai-kb-recall.ts).
// Durable-memory recall for pi, matching the Cursor/Claude sessionStart warm-start
// and adding pi's per-turn retrieval (Cursor's beforeSubmitPrompt cannot inject context).
//
// Thin delegating extension — no logic is duplicated here:
//   - topic + spec resolution comes from `,agent-memory status --json`
//     (single source of truth: scripts/agent_memory.py / hook_common.py)
//   - retrieval + ranking comes from `,ai-kb search` (scripts/ai_kb.py)
//
// Injection points, all via before_agent_start (pi's only context-injection hook):
//   0. Verification prefix: injected at session start, then re-injected when it has
//      decayed — either after a compaction (session_compact summarizes/drops it) or once
//      context-window fill has grown by PREFIX_REINJECT_DELTA_PCT points since the last
//      injection. Context fill + compaction track real decay far better than a turn count
//      (turn size varies wildly). The tmux wrap pastes the same prefix.txt manually;
//      session_context.py injects it once for cursor-agent/claude. before_agent_start is
//      pi's only context-injection hook, so session_compact merely flags a forced
//      re-inject that the next before_agent_start consumes.
//   1. Warm-start (first prompt of a session): query = the active topic spec, gated to a
//      deliberate named topic with a non-empty <topic>.txt. Mirrors session_context.py.
//   2. Per-turn (every substantive prompt): query = the user's actual prompt — the
//      highest-relevance signal — deduped against capsules already injected this session.
//
// Both share the same relevance gate as the Python warm-start: keep only capsules local to
// this workspace or scoped domain/universal, so a large/cross-project KB cannot stuff context.

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent"

const EXEC_TIMEOUT_MS = 6_000
const WARMSTART_LIMIT = 3
const PERTURN_LIMIT = 3
const SEARCH_FETCH = 6
const QUERY_MAX_CHARS = 600
const BODY_MAX_CHARS = 240
const MIN_PROMPT_CHARS = 12
const PREFIX_MAX_CHARS = 3000
// Re-inject the verification prefix once context-window fill has grown by at least this
// many percentage points since it was last injected (decay proxy). Compaction forces a
// re-inject regardless, since it summarizes/drops the prior prefix.
const PREFIX_REINJECT_DELTA_PCT = 20
const CROSS_PROJECT_SCOPES = new Set(["domain", "universal"])

// Same verification-discipline core the tmux wrap pastes manually and that
// session_context.py injects for cursor-agent/claude. Read from the deployed file
// (single source of truth) on each turn it is re-injected (see PREFIX_REINJECT_DELTA_PCT).
//
// prefix.txt holds only the discipline core; framing is owned per consumer because
// placement differs. pi appends before_agent_start messages AFTER the user message
// (agent-session.js builds [user, ...extension messages]), so here the user's prompt
// is ABOVE this injected block — the framing must point backward, never claim a prompt
// follows.
async function readPrefix(pi: ExtensionAPI): Promise<string> {
  const configHome = process.env.XDG_CONFIG_HOME || `${process.env.HOME ?? ""}/.config`
  const path = `${configHome}/tmux/agent_prompts/prefix.txt`
  const result = await pi.exec("cat", [path], { timeout: EXEC_TIMEOUT_MS })
  if (result.killed || result.code !== 0) return ""
  const core = result.stdout.trim().slice(0, PREFIX_MAX_CHARS)
  if (!core) return ""
  return `${core}\n\nApply the discipline above to the user's prompt.`
}

interface MemoryStatus {
  workspace: string
  selected_topic: string
  is_named_topic: boolean
  spec_file: string
  spec_exists: boolean
}

interface Capsule {
  id?: string
  title?: string
  body?: string
  kind?: string
  scope?: string
  workspace_path?: string
}

function collapse(text: string, max: number): string {
  const flat = text.replace(/\s+/g, " ").trim()
  if (flat.length <= max) return flat
  return flat.slice(0, max).trimEnd() + "…"
}

async function memoryStatus(pi: ExtensionAPI, cwd: string): Promise<MemoryStatus | null> {
  const result = await pi.exec(",agent-memory", ["status", "--json", "--workspace", cwd], {
    timeout: EXEC_TIMEOUT_MS,
  })
  if (result.killed || result.code !== 0 || !result.stdout.trim()) return null
  try {
    return JSON.parse(result.stdout) as MemoryStatus
  } catch {
    return null
  }
}

async function searchCapsules(pi: ExtensionAPI, workspace: string, query: string): Promise<Capsule[]> {
  const flat = collapse(query, QUERY_MAX_CHARS)
  if (!flat) return []
  const result = await pi.exec(
    ",ai-kb",
    ["search", flat, "--limit", String(SEARCH_FETCH), "--mode", "bm25", "--workspace", workspace, "--json"],
    { timeout: EXEC_TIMEOUT_MS },
  )
  if (result.killed || result.code !== 0 || !result.stdout.trim()) return []
  try {
    const rows = JSON.parse(result.stdout)
    return Array.isArray(rows) ? (rows as Capsule[]) : []
  } catch {
    return []
  }
}

// Same gate as session_context.py: workspace-local capsules, or deliberately cross-project
// (domain/universal) ones. Skips capsules already injected this session.
function gateAndFormat(rows: Capsule[], workspace: string, seen: Set<string>, limit: number): string[] {
  const lines: string[] = []
  for (const row of rows) {
    if (lines.length >= limit) break
    const sameWorkspace = (row.workspace_path ?? "") === workspace
    const scope = row.scope ?? ""
    if (!sameWorkspace && !CROSS_PROJECT_SCOPES.has(scope)) continue
    const id = row.id ?? ""
    if (id && seen.has(id)) continue
    const title = collapse(row.title ?? "", 200)
    if (!title) continue
    if (id) seen.add(id)
    const kind = row.kind || "note"
    const body = collapse(row.body ?? "", BODY_MAX_CHARS)
    lines.push(body ? `- **${title}** (${kind}): ${body}` : `- **${title}** (${kind})`)
  }
  return lines
}

export default async function (pi: ExtensionAPI) {
  // Disable cleanly if the CLIs are not on PATH (e.g. partial install).
  const probe = await pi.exec(",ai-kb", ["--help"], { timeout: EXEC_TIMEOUT_MS })
  if (probe.code !== 0) {
    console.warn("[ai-kb-recall] ,ai-kb not found in PATH — extension disabled")
    return
  }

  const injectedIds = new Set<string>()
  let warmStartDone = false
  // Context-fill percent at the last prefix injection (null until first injection, or when
  // usage is unknown). A compaction sets forceReinject because it can summarize/drop the prefix.
  let lastPrefixPercent: number | null = null
  let forceReinject = false

  // session_compact cannot inject context (only before_agent_start can), so it flags a
  // forced re-inject that the next before_agent_start consumes.
  pi.on("session_compact", () => {
    forceReinject = true
    lastPrefixPercent = null
  })

  pi.on("before_agent_start", async (event, ctx) => {
    try {
      const status = await memoryStatus(pi, ctx.cwd)
      if (!status) return
      const workspace = status.workspace || ctx.cwd
      const blocks: string[] = []

      // 0. Verification prefix: warm-start, after a compaction, or once context fill has
      //    grown PREFIX_REINJECT_DELTA_PCT points since the last injection.
      const usage = ctx.getContextUsage()
      const percent = usage && usage.percent != null ? usage.percent : null
      const grewEnough =
        lastPrefixPercent != null && percent != null && percent - lastPrefixPercent >= PREFIX_REINJECT_DELTA_PCT
      if (!warmStartDone || forceReinject || grewEnough) {
        const prefix = await readPrefix(pi)
        if (prefix) {
          blocks.push(prefix)
          forceReinject = false
          if (percent != null) lastPrefixPercent = percent
        }
      }

      // 1. Warm-start: once per session, named-topic + spec only (parity with Cursor/Claude).
      if (!warmStartDone) {
        warmStartDone = true
        if (status.is_named_topic && status.spec_exists) {
          const spec = await pi.exec("cat", [status.spec_file], { timeout: EXEC_TIMEOUT_MS })
          const specText = spec.code === 0 ? spec.stdout : ""
          if (specText.trim()) {
            const rows = await searchCapsules(pi, workspace, specText)
            const lines = gateAndFormat(rows, workspace, injectedIds, WARMSTART_LIMIT)
            if (lines.length) {
              blocks.push(
                ["### Relevant Learnings (,ai-kb)", "Surfaced from durable memory for this topic; verify before relying on them.", ...lines].join(
                  "\n",
                ),
              )
            }
          }
        }
      }

      // 2. Per-turn: highest-relevance retrieval using the actual prompt (pi-only capability).
      const prompt = typeof event.prompt === "string" ? event.prompt : ""
      if (prompt.trim().length >= MIN_PROMPT_CHARS) {
        const rows = await searchCapsules(pi, workspace, prompt)
        const lines = gateAndFormat(rows, workspace, injectedIds, PERTURN_LIMIT)
        if (lines.length) {
          blocks.push(
            ["### Relevant Learnings for this request (,ai-kb)", "Matched to your prompt; verify before relying on them.", ...lines].join("\n"),
          )
        }
      }

      if (!blocks.length) return
      return {
        message: {
          customType: "ai-kb-recall",
          content: blocks.join("\n\n"),
          display: true,
        },
      }
    } catch (err) {
      // Fail open: never block a turn on a recall error.
      console.warn("[ai-kb-recall] unexpected error; skipping injection", err)
      return
    }
  })
}
