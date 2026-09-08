// Managed by chezmoi (source: home/dot_pi/agent/exact_extensions/runtime-parity.ts).
// Pi runtime defaults that mirror the shared Cursor contracts.

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent"
import { readFileSync, realpathSync } from "node:fs"
import { homedir } from "node:os"
import { join } from "node:path"

const SEARCH_TOOLS = ["grep", "find", "ls"]
const TOOL_SELECTION_FLAGS = ["--tools", "-t", "--exclude-tools", "-xt", "--no-tools", "-nt", "--no-builtin-tools", "-nbt"]

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
  pi.on("session_start", () => {
    enableSearchTools(pi)
  })

  pi.on("before_agent_start", (event) => {
    if (process.env.PI_SUBAGENT_CHILD === "1" || /^\[DELEGATION BOUNDARY\]$/m.test(event.systemPrompt ?? "")) return
    const sopPath = join(process.env.HOME || homedir(), "AGENTS.md")
    try {
      const canonical = realpathSync(sopPath)
      const loaded = event.systemPromptOptions?.contextFiles?.some(({ path }) => {
        try { return realpathSync(path) === canonical } catch { return false }
      })
      if (loaded) return
      const sop = readFileSync(canonical, "utf8").trim()
      if (!sop || event.systemPrompt.includes(sop)) return
      return {
        systemPrompt: `${event.systemPrompt}\n\n<project_context>\n<project_instructions path=${JSON.stringify(sopPath)}>\n${sop}\n</project_instructions>\n</project_context>`,
      }
    } catch (error) {
      console.error(`Could not load global SOP ${sopPath}: ${error}`)
    }
  })
}
