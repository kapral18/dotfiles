// Managed by chezmoi (source: home/dot_pi/agent/exact_extensions/read-gate.ts).
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent"
import { spawn } from "node:child_process"
import { homedir } from "node:os"
import { join } from "node:path"

// Hash-gated re-reads (see ~/.agents/hooks/read_gate.py): a second whole-file read whose
// bytes are byte-identical to a read already in this session is refused with a pointer to
// that read; changed files, slices, pipes and first reads pass. The Python hook owns the
// decision; this extension only maps Pi's tool_call / tool_result events onto the
// Claude-style hook payload and honours a block. Fail-open everywhere.

const GATE_TIMEOUT_MS = 10_000
const GATE_STDOUT_MAX_BYTES = 64 * 1024
const GATED_TOOLS = new Set(["read", "bash"])

interface GateProcessResult {
  code: number
  killed: boolean
  stdout: string
}

function gatePath(): string {
  const home = process.env.HOME || homedir()
  return join(home, ".agents", "hooks", "read_gate.py")
}

function runGate(payload: Record<string, unknown>): Promise<GateProcessResult> {
  return new Promise((resolve) => {
    let stdout = ""
    let stdoutBytes = 0
    let killed = false
    let settled = false
    const child = spawn(gatePath(), [], { stdio: ["pipe", "pipe", "ignore"] })
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
    child.stdin.end(JSON.stringify(payload))
  })
}

function resultText(content: unknown): string {
  if (!Array.isArray(content)) return ""
  return content
    .map((block) => (block && typeof block === "object" && typeof (block as { text?: unknown }).text === "string" ? (block as { text: string }).text : ""))
    .join("\n")
}

export default function (pi: ExtensionAPI) {
  const base = (ctx: { cwd: string; sessionManager: { getSessionId(): string; getSessionFile?(): string | undefined } }) => ({
    session_id: ctx.sessionManager.getSessionId(),
    transcript_path: ctx.sessionManager.getSessionFile?.() ?? "",
    cwd: ctx.cwd,
  })

  pi.on("tool_call", async (event, ctx) => {
    if (!GATED_TOOLS.has(event.toolName)) return
    try {
      const result = await runGate({
        ...base(ctx),
        hook_event_name: "PreToolUse",
        tool_name: event.toolName,
        tool_input: event.input,
        tool_use_id: event.toolCallId,
      })
      if (result.killed || result.code !== 0 || !result.stdout.trim()) return
      const output = JSON.parse(result.stdout)
      if (output?.decision === "block" && typeof output.reason === "string") {
        return { block: true, reason: output.reason }
      }
    } catch {
      // fail open
    }
    return
  })

  pi.on("tool_result", async (event, ctx) => {
    if (!GATED_TOOLS.has(event.toolName) || event.isError) return
    try {
      await runGate({
        ...base(ctx),
        hook_event_name: "PostToolUse",
        tool_name: event.toolName,
        tool_input: event.input,
        tool_use_id: event.toolCallId,
        tool_response: resultText(event.content),
      })
    } catch {
      // fail open
    }
  })
}
