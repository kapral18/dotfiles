// Managed by chezmoi (source: home/dot_pi/agent/extensions/runtime-parity.ts).
// Pi runtime defaults and safety hooks that mirror the shared Cursor contracts.

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent"
import { spawn } from "node:child_process"
import { homedir } from "node:os"
import { join } from "node:path"

const SEARCH_TOOLS = ["grep", "find", "ls"]
const TOOL_SELECTION_FLAGS = ["--tools", "-t", "--exclude-tools", "-xt", "--no-tools", "-nt", "--no-builtin-tools", "-nbt"]
const GATE_TIMEOUT_MS = 10_000
const GATE_STDOUT_MAX_BYTES = 64 * 1024
const BLOCK_REASON = "Git commit/push requires explicit approval; the Pi safety gate refused this command."

interface GateProcessResult {
  code: number
  killed: boolean
  stdout: string
}

type GateDecision = "allow" | "ask" | "deny"

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

function runGitGate(command: string): Promise<GateProcessResult> {
  const home = process.env.HOME || homedir()
  const script = join(home, ".agents", "hooks", "gemini-git-gate.py")
  return new Promise((resolve) => {
    let stdout = ""
    let stdoutBytes = 0
    let killed = false
    let settled = false
    const child = spawn(script, [], { stdio: ["pipe", "pipe", "ignore"] })
    const finish = (code: number) => {
      if (settled) return
      settled = true
      clearTimeout(timer)
      resolve({ code, killed, stdout })
    }
    const timer = setTimeout(() => {
      killed = true
      child.kill("SIGKILL")
    }, GATE_TIMEOUT_MS)

    child.stdout.on("data", (chunk: Buffer) => {
      stdoutBytes += chunk.length
      if (stdoutBytes > GATE_STDOUT_MAX_BYTES) {
        killed = true
        child.kill("SIGKILL")
        return
      }
      stdout += chunk.toString()
    })
    child.stdin.on("error", () => {})
    child.on("error", () => finish(1))
    child.on("close", (code) => finish(code ?? 1))
    child.stdin.end(JSON.stringify({ hook_event_name: "beforeShellExecution", command }))
  })
}

async function gitGateDecision(command: string): Promise<GateDecision> {
  const result = await runGitGate(command)
  if (result.killed || result.code !== 0) return "deny"
  try {
    const output = JSON.parse(result.stdout)
    if (output?.permission === "allow" || output?.decision === "allow") return "allow"
    if (output?.permission === "ask") return "ask"
    return "deny"
  } catch {
    return "deny"
  }
}

export default function (pi: ExtensionAPI) {
  pi.on("session_start", () => {
    enableSearchTools(pi)
  })

  pi.on("tool_call", async (event, ctx) => {
    if (event.toolName !== "bash" || !("command" in event.input) || typeof event.input.command !== "string") return

    const decision = await gitGateDecision(event.input.command)
    if (decision === "allow") return
    if (decision === "ask" && ctx.hasUI) {
      const approved = await ctx.ui.confirm(
        "Git commit/push safety gate",
        `Command:\n\n${event.input.command}\n\nAllow only when the user explicitly requested this commit or push.`,
      )
      if (approved) return
    }
    return { block: true, reason: BLOCK_REASON }
  })
}
