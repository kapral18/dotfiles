// Managed by chezmoi (source: home/dot_pi/agent/exact_extensions/runtime-parity.ts).
// Pi runtime defaults that mirror the shared Cursor contracts.

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent"
import { readFileSync, realpathSync } from "node:fs"
import { homedir } from "node:os"
import { join } from "node:path"

const SEARCH_TOOLS = ["grep", "find", "ls"]
const TOOL_SELECTION_FLAGS = ["--tools", "-t", "--exclude-tools", "-xt", "--no-tools", "-nt", "--no-builtin-tools", "-nbt"]
const DISPATCH_RULE = 'Root Pi dispatch: use a named managed profile with agentScope:"user", acceptance:false and fresh context. Do not use project-discovered replacements or per-call model/skill overrides.'

function hasExplicitToolSelection(argv: string[]): boolean {
  return argv.some((arg) =>
    TOOL_SELECTION_FLAGS.some((flag) => arg === flag || arg.startsWith(`${flag}=`)),
  )
}

function enableSearchTools(pi: ExtensionAPI): void {
  if (hasExplicitToolSelection(process.argv.slice(2))) return
  const active = pi.getActiveTools()
  const merged = [...active]
  for (const tool of SEARCH_TOOLS) {
    if (!merged.includes(tool)) merged.push(tool)
  }
  if (merged.length !== active.length) pi.setActiveTools(merged)
}

export default function (pi: ExtensionAPI) {
  pi.on("tool_call", (event) => {
    if (event.toolName !== "subagent") return
    const input = event.input as Record<string, unknown>
    if (process.env.PI_SUBAGENT_CHILD === "1") {
      return { block: true, reason: "A delegated worker MUST NOT invoke subagents or manage other runs. Return the assigned packet result to the root." }
    }
    // Keep observation/cancellation, not resume/steer recovery, scheduling or
    // a second workflow engine. Independent root packets may still use async.
    if (input.action !== undefined) {
      if (["list", "status", "debug.run", "stop", "interrupt"].includes(String(input.action))) return
      return { block: true, reason: "The root owns packet lifecycles. Resume, revival, scheduling and nested workflow management are disabled; use a new authorized packet, or inspect/stop an existing run." }
    }
    if (input.workflow !== undefined || input.workflowScript !== undefined || input.workflowScriptPath !== undefined
      || input.chain !== undefined || input.parallel !== undefined || input.gate !== undefined || input.agentContract !== undefined) {
      return { block: true, reason: "Dispatch one ready leaf packet per call. Do not embed workflow engines, acceptance gates or repair chains. Independent root packets may run concurrently." }
    }
    if (input.acceptance !== false || input.agentScope !== "user" || (input.context !== undefined && input.context !== "fresh")
      || input.model !== undefined || input.skill !== undefined || input.skills !== undefined || input.steeringRecovery === true) {
      return { block: true, reason: 'Leaf dispatch requires agentScope:"user", acceptance:false and fresh context (or the fresh default). Do not replace managed profiles through project discovery or override their model/role skills. Only the root owns final acceptance.' }
    }
  })

  pi.on("session_start", () => {
    enableSearchTools(pi)
  })

  pi.on("before_agent_start", (event) => {
    if (process.env.PI_SUBAGENT_CHILD === "1" || /^\[DELEGATION BOUNDARY\]$/m.test(event.systemPrompt ?? "")) return
    const systemPrompt = event.systemPrompt.includes(DISPATCH_RULE) ? event.systemPrompt : `${event.systemPrompt}\n\n${DISPATCH_RULE}`
    const sopPath = join(process.env.HOME || homedir(), "AGENTS.md")
    try {
      const canonical = realpathSync(sopPath)
      const loaded = event.systemPromptOptions?.contextFiles?.some(({ path }) => {
        try { return realpathSync(path) === canonical } catch { return false }
      })
      if (loaded) return { systemPrompt }
      const sop = readFileSync(canonical, "utf8").trim()
      if (!sop || systemPrompt.includes(sop)) return { systemPrompt }
      return {
        systemPrompt: `${systemPrompt}\n\n<project_context>\n<project_instructions path=${JSON.stringify(sopPath)}>\n${sop}\n</project_instructions>\n</project_context>`,
      }
    } catch (error) {
      console.error(`Could not load global SOP ${sopPath}: ${error}`)
      return { systemPrompt }
    }
  })
}
