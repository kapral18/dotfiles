/** The intent-guard adapter shared by Pi, OMP, and OpenCode: forwards session events to `,task hook` (~/AGENTS.md §3 step 0). */

export interface Answer {
  context?: string
  deny?: string
  note?: string
  instructions?: string
  block?: string
}

export interface ExecResult {
  stdout: string
  code: number
}

export type Exec = (command: string, args: string[], options?: { cwd?: string; timeout?: number }) => Promise<ExecResult>

export interface GuardContext {
  cwd: string
  sessionManager: { getSessionId(): string }
}

// Tools that change files by path, or execute code whose writes need before/after snapshots.
const WRITE_TOOLS = new Set(["edit", "write", "multiedit", "apply_patch", "notebook_edit", "ast_edit"])
const SHELL_TOOLS = new Set(["bash", "powershell", "shell", "exec_command", "write_stdin", "python", "eval"])

export const isShellTool = (tool: string): boolean => SHELL_TOOLS.has(tool.toLowerCase())

/** The paths a file-writing tool call names, or undefined for a tool that writes no file. */
export function writePaths(tool: string, input: Record<string, unknown>): string[] | undefined {
  if (!WRITE_TOOLS.has(tool.toLowerCase())) return undefined
  const listed = Array.isArray(input.paths) ? input.paths : []
  return [input.path, input.file_path, ...listed].filter((path): path is string => typeof path === "string" && path !== "")
}

/** The text blocks of an agent message, joined. */
export function messageText(message: unknown): string {
  if (!message || typeof message !== "object" || !("content" in message)) return ""
  const content = (message as { content: unknown }).content
  if (typeof content === "string") return content
  if (!Array.isArray(content)) return ""
  return content
    .filter((block): block is { type: "text"; text: string } => block?.type === "text" && typeof block.text === "string")
    .map((block) => block.text)
    .join("\n")
}

/** The last assistant message's text in a list of agent messages. */
export function lastAnswer(messages: readonly unknown[]): string {
  for (let index = messages.length - 1; index >= 0; index--) {
    const message = messages[index] as { role?: unknown } | undefined
    if (message?.role === "assistant") return messageText(message)
  }
  return ""
}

/** A caller of `,task hook <event>`; a failed or missing `,task` answers nothing, so the session goes on unguarded. */
export function createIntentGuard(harness: "pi" | "omp" | "opencode", exec: Exec) {
  return async function task(event: string, input: Record<string, unknown>, ctx: GuardContext, session?: string): Promise<Answer> {
    const payload = JSON.stringify({ ...input, cwd: ctx.cwd, session: session ?? ctx.sessionManager.getSessionId() })
    try {
      const run = await exec(",task", ["hook", event, "--harness", harness, "--input", payload], { cwd: ctx.cwd, timeout: 15_000 })
      if (run.code !== 0) return {}
      const answer: unknown = JSON.parse(run.stdout)
      return answer && typeof answer === "object" ? (answer as Answer) : {}
    } catch {
      return {}
    }
  }
}
