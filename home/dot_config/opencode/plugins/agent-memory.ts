// Managed by chezmoi (source: home/dot_config/opencode/plugins/agent-memory.ts).
import type { Plugin } from "@opencode-ai/plugin"
import { existsSync } from "node:fs"
import { homedir } from "node:os"
import { join } from "node:path"

// Agent-memory plugin — session-context warm-start + worklog recording,
// bringing OpenCode to parity with the Claude/Cursor/Gemini hooks.
//
// Thin delegating plugin: all logic lives in the shared hook scripts
// (~/.agents/hooks/session_context.py and worklog_dispatcher.sh, sourced from
// home/exact_dot_agents/exact_hooks/) — topic/spec resolution, worklog
// format, and KB warm-start stay single-source. This file only adapts the
// OpenCode plugin events to the hooks' stdin/stdout JSON protocol.
//
//   - experimental.chat.system.transform: fetches the SessionStart context
//     once per session (cached, including negative results) and appends it
//     to the system prompt of every request — system is rebuilt per request,
//     so re-appending is idempotent, never accumulating.
//   - tool.execute.after: synthesizes a PostToolUse payload for the worklog
//     dispatcher. `duration`/`status` are not exposed by the plugin API and
//     are simply omitted (the recorder drops empty fields).
//   - tool.execute.before / tool.execute.after on `read` and `bash`: the shared
//     read gate (~/.agents/hooks/read_gate.py). A byte-identical whole-file
//     re-read whose earlier result is still intact in the OpenCode store
//     (~/.local/share/opencode/opencode.db, `part` rows) is refused by throwing;
//     OpenCode records the thrown message as the tool error the model reads.

export const AgentMemoryPlugin: Plugin = async ({ $, directory }) => {
  const hooksDir = join(homedir(), ".agents", "hooks")
  const sessionCtx = join(hooksDir, "session_context.py")
  const recorder = join(hooksDir, "worklog_dispatcher.sh")
  const perturn = join(hooksDir, "perturn_recall.py")
  const readGate = join(hooksDir, "read_gate.py")
  const store = join(homedir(), ".local", "share", "opencode", "opencode.db")
  const gatedTools = new Set(["read", "bash"])
  if (!existsSync(sessionCtx) || !existsSync(recorder)) {
    console.warn("[agent-memory] ~/.agents/hooks scripts not found — plugin disabled")
    return {}
  }

  const contextBySession = new Map<string, string>()

  async function runHook(script: string, payload: Record<string, unknown>): Promise<string> {
    try {
      const json = JSON.stringify(payload)
      const result = await $`echo ${json} | python3 ${script}`.quiet().nothrow()
      const parsed = JSON.parse(String(result.stdout).trim() || "{}")
      return String(parsed?.hookSpecificOutput?.additionalContext ?? "")
    } catch {
      // hook failure must never break the chat
      return ""
    }
  }

  async function runJsonHook(script: string, payload: Record<string, unknown>): Promise<Record<string, unknown>> {
    try {
      const json = JSON.stringify(payload)
      const result = await $`echo ${json} | python3 ${script}`.quiet().nothrow()
      const parsed = JSON.parse(String(result.stdout).trim() || "{}")
      return parsed && typeof parsed === "object" ? parsed : {}
    } catch {
      return {}
    }
  }

  function gatePayload(event: string, input: { tool: string; sessionID: string; callID: string }, args: unknown) {
    return {
      hook_event_name: event,
      cwd: directory,
      session_id: input.sessionID,
      tool_name: input.tool,
      tool_input: args ?? {},
      tool_use_id: input.callID,
      transcript_path: store,
    }
  }

  async function warmStart(sessionID: string): Promise<string> {
    const cached = contextBySession.get(sessionID)
    if (cached !== undefined) return cached
    const context = await runHook(sessionCtx, {
      hook_event_name: "SessionStart",
      cwd: directory,
      session_id: sessionID,
      warm_embedder: true,
    })
    contextBySession.set(sessionID, context)
    return context
  }

  return {
    "experimental.chat.system.transform": async (input, output) => {
      if (!input.sessionID) return
      const context = await warmStart(input.sessionID)
      if (context) output.system.push(context)
    },

    // Per-turn recall, injected into the CURRENT message (never a new cycle):
    // delegates to the same perturn_recall.py Claude Code uses, which owns the
    // relevance gates and the per-session seen-file dedup (keyed by session_id,
    // shared with the warm-start above).
    "chat.message": async (input, output) => {
      if (!existsSync(perturn) || !input.sessionID || !output.message?.id) return
      const prompt = output.parts
        .filter((p) => p.type === "text" && typeof p.text === "string")
        .map((p) => (p as { text: string }).text)
        .join("\n")
      if (!prompt.trim()) return
      const context = await runHook(perturn, {
        hook_event_name: "UserPromptSubmit",
        cwd: directory,
        session_id: input.sessionID,
        prompt,
      })
      if (!context) return
      output.parts.push({
        id: `prt_aikb_${output.message.id}`,
        sessionID: input.sessionID,
        messageID: output.message.id,
        type: "text",
        text: context,
        synthetic: true,
      })
    },

    "tool.execute.before": async (input, output) => {
      if (!gatedTools.has(input.tool) || !existsSync(readGate)) return
      const verdict = await runJsonHook(readGate, gatePayload("PreToolUse", input, output?.args))
      if (verdict.decision === "block" && typeof verdict.reason === "string" && verdict.reason) {
        throw new Error(verdict.reason)
      }
    },

    "tool.execute.after": async (input, output) => {
      if (gatedTools.has(input.tool) && existsSync(readGate)) {
        await runJsonHook(readGate, {
          ...gatePayload("PostToolUse", input, input.args),
          tool_response: typeof output?.output === "string" ? output.output : "",
        })
      }
      try {
        const payload = JSON.stringify({
          hook_event_name: "PostToolUse",
          cwd: directory,
          session_id: input.sessionID,
          tool_name: input.tool,
          command: typeof output?.title === "string" ? output.title : "",
          output: typeof output?.output === "string" ? output.output.slice(0, 2000) : "",
        })
        const result = await $`echo ${payload} | ${recorder}`.quiet().nothrow()
        const status = result as { code?: number; exitCode?: number; stderr?: unknown }
        const exitCode = status.exitCode ?? status.code ?? 0
        if (exitCode !== 0) {
          console.warn(`[agent-memory] worklog hook exited ${exitCode}: ${String(status.stderr ?? "").trim()}`)
        }
      } catch (error) {
        console.warn("[agent-memory] worklog hook failed; tool execution continues", error)
      }
    },
  }
}
