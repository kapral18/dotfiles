import { afterAll, describe, expect, it, mock } from "bun:test"
import { existsSync, mkdtempSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join, resolve } from "node:path"
import { createIntentGuard, lastAnswer, writePaths } from "../../home/exact_lib/exact_shared/intent_guard.ts"

const root = resolve(import.meta.dir, "../..")
const temp = mkdtempSync(join(tmpdir(), "intent-guard-tests-"))
const realHome = process.env.HOME
afterAll(() => {
  process.env.HOME = realHome
  rmSync(temp, { recursive: true, force: true })
})
const adapters = {
  pi: "home/dot_pi/agent/exact_extensions/intent-guard.ts.tmpl",
  omp: "home/dot_omp/private_agent/extensions/intent-guard.ts.tmpl",
} as const
// The host provides Pi's schema builder; the test stands in for it.
mock.module("@earendil-works/pi-ai", () => ({ Type: { Object: (shape: unknown) => shape, String: () => ({}), Integer: () => ({}), Optional: (type: unknown) => type } }))
// Materialize every adapter before the first import, as chezmoi does before runtime startup.
for (const [name, source] of Object.entries(adapters)) {
  writeFileSync(join(temp, `${name}.ts`), readFileSync(join(root, source), "utf8").replace(
    "{{ .chezmoi.homeDir }}/lib/shared/intent_guard.ts",
    join(root, "home/exact_lib/exact_shared/intent_guard.ts"),
  ).replace("{{ .chezmoi.homeDir }}/lib/shared/task_context.ts", join(root, "home/exact_lib/exact_shared/task_context.ts")))
}

type Handler = (event: any, ctx: any) => Promise<any>

// A fake host: `,task hook <event>` answers from `answers`; every call is recorded.
async function load(name: "pi" | "omp", answers: Record<string, unknown> = {}) {
  const handlers = new Map<string, Handler>()
  const calls: { event: string; input: Record<string, unknown>; cwd?: string }[] = []
  const messages: unknown[] = []
  const tools: { name: string; execute: (id: string, params: { entryId: string; offset?: number }, signal: AbortSignal | undefined, update: undefined, ctx: unknown) => Promise<unknown> }[] = []
  const pi = {
    registerTool: (tool: typeof tools[number]) => { tools.push(tool) },
    on: (event: string, handler: Handler) => { handlers.set(event, handler) },
    sendMessage: (message: unknown, options: unknown) => { messages.push({ message, options }) },
    exec: async (command: string, args: string[], options?: { cwd?: string }) => {
      expect(command).toBe(",task")
      expect(args[4]).toBe("--input-file")
      expect(statSync(args[5]).mode & 0o077).toBe(0)
      calls.push({ event: args[1], input: JSON.parse(readFileSync(args[5], "utf8")), cwd: options?.cwd })
      const answer = answers[args[1]]
      return { stdout: JSON.stringify(typeof answer === "function" ? await answer() : answer ?? {}), stderr: "", code: 0, killed: false }
    },
  }
  const module = await import(join(temp, `${name}.ts`))
  module.default(pi)
  const ctx = { cwd: "/repo", sessionManager: { getSessionId: () => "s1", getLeafId: () => "leaf", getBranch: () => [] }, agent: { kind: "main" }, hasPendingMessages: () => false }
  const fire = (event: string, payload: unknown, agent = "main", overrides = {}) => handlers.get(event)!(payload, { ...ctx, agent: { kind: agent }, ...overrides })
  return { calls, fire, handlers, messages, tools }
}

describe("shared intent guard", () => {
  it("answers nothing when it cannot make its payload file", async () => {
    const before = process.env.TMPDIR
    process.env.TMPDIR = join(temp, "missing")
    try {
      const guard = createIntentGuard("pi", async () => ({ stdout: '{"deny":"x"}', stderr: "", code: 0, killed: false }))
      expect(await guard("prompt", {}, { cwd: "/repo", sessionManager: { getSessionId: () => "s1" } } as any)).toEqual({})
    } finally {
      process.env.TMPDIR = before
    }
  })

  it("names the paths only of file-writing tools", () => {
    expect(writePaths("bash", { command: "ls" })).toBeUndefined()
    expect(writePaths("edit", { path: "a.ts", paths: ["b.ts", 3] })).toEqual(["a.ts", "b.ts"])
    expect(writePaths("Write", { file_path: "/x/c.ts" })).toEqual(["/x/c.ts"])
  })

  it("reads the last assistant answer", () => {
    const messages = [
      { role: "assistant", content: [{ type: "text", text: "first" }] },
      { role: "user", content: "next" },
      { role: "assistant", content: [{ type: "thinking", thinking: "x" }, { type: "text", text: "Done." }] },
    ]
    expect(lastAnswer(messages)).toBe("Done.")
  })

  it("answers nothing when ,task fails or prints garbage", async () => {
    const ctx = { cwd: "/repo", sessionManager: { getSessionId: () => "s1" } }
    const failed = createIntentGuard("pi", async () => ({ stdout: "", code: 127 }))
    expect(await failed("stop", {}, ctx)).toEqual({})
    const garbage = createIntentGuard("pi", async () => ({ stdout: "not json", code: 0 }))
    expect(await garbage("stop", {}, ctx)).toEqual({})
    const thrown = createIntentGuard("pi", async () => { throw new Error("ENOENT") })
    expect(await thrown("stop", {}, ctx)).toEqual({})
  })

  it("passes a large payload through a private file that is removed afterwards", async () => {
    const ctx = { cwd: "/repo", sessionManager: { getSessionId: () => "s1" } }
    let seen: { args: string[]; text: string } | undefined
    const guard = createIntentGuard("pi", async (_command, args) => {
      seen = { args, text: readFileSync(args[5], "utf8") }
      return { stdout: JSON.stringify({ deny: "no card" }), code: 0 }
    })
    const content = "x".repeat(2_000_000)
    expect(await guard("tool", { tool: "write", content }, ctx)).toEqual({ deny: "no card" })
    expect(seen?.args.join(" ").length).toBeLessThan(1000)
    expect(JSON.parse(seen?.text ?? "{}").content).toBe(content)
    expect(existsSync(seen?.args[5] ?? "")).toBe(false)
  })
})

describe("pi adapter", () => {
  it("SHOULD checkpoint completed tool turns once and reuse it for the next provider call", async () => {
    const { fire, calls } = await load("pi", { checkpoint: { context: "Goal: continue working" }, stop: { block: "Do not stop" } })

    const actual = await fire("turn_end", { outcome: "completed", entries: [], context: { contextEntries: [] } })
    const projected = await fire("context", { messages: [] })

    expect(actual.entries).toEqual([{ type: "custom", customType: "task-context", data: "Goal: continue working" }])
    expect(actual).not.toHaveProperty("continue")
    expect(projected.messages[0].content).toBe("Goal: continue working")
    expect(calls.map(call => call.event)).toEqual(["checkpoint"])
  })

  it("SHOULD refresh one checkpoint and preserve a previous boundary proposal and continuation", async () => {
    const { fire } = await load("pi", { checkpoint: { context: "Goal: current; F1 open; review v2" } })
    const previous = { type: "custom", customType: "review-state", data: { round: 4 } }
    const event = { outcome: "completed", entries: [previous], continue: true, context: { contextMessages: [], contextEntries: [] } }

    const actual = await fire("turn_end", event)

    expect(actual.entries).toEqual([previous, { type: "custom", customType: "task-context", data: "Goal: current; F1 open; review v2" }])
    expect(actual).not.toHaveProperty("continue") // Pi retains the preceding extension's true value.
  })

  it("SHOULD avoid archival during signal-free settlement", async () => {
    const { fire } = await load("pi", { checkpoint: { context: "Goal: old task" } })
    const old = { role: "toolResult", toolCallId: "old-call", toolName: "bash", isError: false, timestamp: 1, content: [{ type: "text", text: "old output".repeat(6000) }] }
    const recent = { ...old, toolCallId: "new-call", content: [{ type: "text", text: "recent output".repeat(3000) }] }
    const event = {
      outcome: "completed", entries: [], context: { contextMessages: [], contextEntries: [
        { sourceEntry: { type: "message", id: "old-entry", parentId: null, timestamp: "2026-10-27", message: old }, messages: [old] },
        { sourceEntry: { type: "message", id: "new-entry", parentId: "old-entry", timestamp: "2026-10-27", message: recent }, messages: [recent] },
      ] },
    }

    const actual = await fire("agent_before_settle", event, "main", { signal: undefined })

    expect(actual).toBeUndefined()
  })

  it("SHOULD preserve context when the checkpoint backend fails", async () => {
    const { fire } = await load("pi")
    const messages = [{ role: "user", content: "Keep this" }]

    const actual = await fire("context", { messages })

    expect(actual).toBeUndefined()
    expect(messages).toEqual([{ role: "user", content: "Keep this" }])
  })

  it("SHOULD avoid persistent edits when the checkpoint backend fails", async () => {
    const { fire } = await load("pi")

    const actual = await fire("turn_end", { outcome: "completed", entries: [], context: { contextEntries: [] } })

    expect(actual).toBeUndefined()
  })

  it.each(["input", "session", "leaf", "abort"])("SHOULD discard a proposal after an in-flight %s change", async (change) => {
    let changed = false
    const controller = new AbortController()
    const { fire } = await load("pi", { checkpoint: () => { changed = true; if (change === "abort") controller.abort(); return { context: "Old task" } } })
    const ctx = {
      hasPendingMessages: () => change === "input" && changed,
      sessionManager: {
        getSessionId: () => change === "session" && changed ? "new-session" : "s1",
        getLeafId: () => change === "leaf" && changed ? "new-leaf" : "leaf",
        getBranch: () => [],
      },
      signal: controller.signal,
    }

    const actual = await fire("turn_end", { outcome: "completed", entries: [], context: { contextEntries: [] } }, "main", ctx)

    expect(actual).toBeUndefined()
  })

  it("SHOULD leave a boundary with queued user input unchanged", async () => {
    const { fire } = await load("pi", { checkpoint: { context: "Goal" }, stop: { block: "Continue" } })

    const actual = await fire("agent_before_settle", { outcome: "completed" }, "main", { hasPendingMessages: () => true })

    expect(actual).toBeUndefined()
  })

  it("SHOULD reject cancelled history retrieval", async () => {
    const { tools } = await load("pi")

    const actual = tools[0].execute("id", { entryId: "entry" }, AbortSignal.abort(), undefined, {})

    await expect(actual).rejects.toThrow("cancelled")
  })

  it("adds the prompt notes the checkpoint lacks to a typed prompt only", async () => {
    const { calls, fire } = await load("pi", { prompt: { context: "Intent card for this task\n\nThis message corrects you", notes: "This message corrects you" } })
    const result = await fire("before_agent_start", { messageType: "user", prompt: "no, add the button" })
    expect(result).toEqual({ message: { customType: "intent-guard", content: "This message corrects you", display: false } })
    expect(calls).toEqual([{ event: "prompt", input: { text: "no, add the button", cwd: "/repo", session: "s1" }, cwd: "/repo" }])
    expect(await fire("before_agent_start", { messageType: "custom", message: {} })).toBeUndefined()
  })

  it("records typed input as the user's words and nothing an extension sends", async () => {
    const { calls, fire } = await load("pi")
    expect(await fire("input", { text: "from an extension", source: "extension" })).toBeUndefined()
    expect(calls).toEqual([])
    await fire("input", { text: "keep CSV", source: "interactive" })
    expect(calls.map(({ event, input }) => [event, input.text])).toEqual([["user", "keep CSV"]])
  })

  it("blocks an uncarded edit before it runs and counts the step after", async () => {
    const { calls, fire } = await load("pi", { tool: { deny: "no intent card", note: "zoom out" } })
    await fire("tool_call", { toolName: "bash", toolCallId: "shell-1", input: { command: "ls" } })
    expect(await fire("tool_call", { toolName: "edit", input: { path: "src/a.ts" } })).toEqual({ block: true, reason: "no intent card" })
    expect(calls[1].input).toMatchObject({ tool: "edit", paths: ["src/a.ts"], write: true, phase: "before" })
    expect(calls[0].input).toMatchObject({ tool: "bash", phase: "before", call_id: "shell-1" })

    const result = await fire("tool_result", { toolName: "bash", toolCallId: "shell-1", input: { command: "ls" }, content: [{ type: "text", text: "out" }] })
    expect(result).toEqual({ content: [{ type: "text", text: "out" }, { type: "text", text: "zoom out" }] })
    expect(calls[2].input).toMatchObject({ tool: "bash", paths: [], write: false, phase: "after", call_id: "shell-1" })
  })

  it("guards an edit a codemode script makes", async () => {
    const { fire } = await load("pi", { tool: { deny: "no intent card" } })
    expect(await fire("tool_call", { toolName: "edit", parentToolCallId: "p", input: { path: "a" } })).toEqual({ block: true, reason: "no intent card" })
  })

  it("continues a completed run while the card has open items", async () => {
    const { calls, fire } = await load("pi", { stop: { block: "intent-guard: open items" } })
    const event = {
      outcome: "completed",
      entries: [],
      context: { canContinue: false, contextMessages: [{ role: "assistant", content: [{ type: "text", text: "Done." }] }] },
    }
    expect(await fire("agent_before_settle", event)).toEqual({
      entries: [{ type: "custom_message", customType: "intent-guard", content: "intent-guard: open items", display: true }],
      continue: true,
    })
    expect(calls[0].input.answer).toBe("Done.")
    expect(await fire("agent_before_settle", { ...event, outcome: "aborted" })).toBeUndefined()
  })

  it("marks compaction so the next tool call shows the card", async () => {
    const { calls, fire } = await load("pi")
    await fire("session_before_compact", {})
    expect(calls[0].event).toBe("compact")
  })
})

describe("omp adapter", () => {
  it("retains background snapshots and finishes them on terminal updates", async () => {
    const { calls, fire, messages } = await load("omp", { tool: { note: "background scope note" } })
    await fire("tool_result", { toolName: "bash", toolCallId: "job-1", input: { async: true }, details: { async: { state: "running", jobId: "j1" } }, content: [] })
    expect(calls[0].input).toMatchObject({ background: true, phase: "after", call_id: "job-1" })
    const update = { toolName: "bash", toolCallId: "job-1", partialResult: { details: { async: { state: "running" } } } }
    await fire("tool_execution_update", update)
    expect(calls).toHaveLength(1)
    for (const state of ["completed", "failed", "cancelled"]) {
      await fire("tool_execution_update", { ...update, partialResult: { details: { async: { state } } } })
    }
    expect(calls.slice(1).map(({ input }) => [input.call_id, input.phase])).toEqual([["job-1", "complete"], ["job-1", "complete"], ["job-1", "complete"]])
    expect(messages).toHaveLength(3)
    expect(messages[0]).toEqual({ message: { customType: "intent-guard", content: "background scope note", display: false }, options: { triggerTurn: false } })
    await fire("tool_execution_update", { ...update, partialResult: { details: { async: { state: "completed" } } } }, "sub")
    expect(calls).toHaveLength(4)
  })

  it("pairs each shell snapshot with its result and preserves normalized hashline paths", async () => {
    const { calls, fire } = await load("omp")
    for (const toolCallId of ["one", "two"]) await fire("tool_call", { toolName: "bash", toolCallId, input: { command: "true" } })
    for (const toolCallId of ["two", "one"]) await fire("tool_result", { toolName: "bash", toolCallId, input: {}, content: [] })
    expect(calls.map(({ input }) => [input.call_id, input.phase])).toEqual([["one", "before"], ["two", "before"], ["two", "after"], ["one", "after"]])
    const patch = "*** Begin Patch\n[src/a.py#abcd]\nMV docs/new name.py\n*** End Patch"
    await fire("tool_call", { toolName: "edit", toolCallId: "edit", input: { path: "src/a.py", input: patch } })
    expect(calls[4].input).toMatchObject({ paths: ["src/a.py"], patch, phase: "before" })
  })

  it("leaves subagents and advisors alone", async () => {
    const { calls, fire } = await load("omp", { prompt: { context: "card" }, tool: { deny: "no card" }, stop: { block: "open" } })
    expect(await fire("before_agent_start", { prompt: "task" }, "sub")).toBeUndefined()
    expect(await fire("tool_call", { toolName: "edit", input: { path: "a" } }, "sub")).toBeUndefined()
    expect(await fire("session_stop", { session_id: "c1" }, "sub")).toBeUndefined()
    expect(calls).toEqual([])
  })

  it("adds the scope note as trusted context and the patch for apply_patch", async () => {
    const { calls, fire } = await load("omp", { tool: { note: "lib/x.py is outside" } })
    const patch = "*** Begin Patch\n*** Update File: lib/x.py\n"
    expect(await fire("tool_result", { toolName: "apply_patch", input: { input: patch }, content: [] })).toEqual({ additionalContext: "lib/x.py is outside" })
    expect(calls[0].input).toMatchObject({ tool: "apply_patch", patch, write: true })
  })

  it("keeps the card through compaction and continues an unfinished stop", async () => {
    const { calls, fire } = await load("omp", { compact: { instructions: "Keep this intent card verbatim" }, stop: { block: "open items" } })
    expect(await fire("session.compacting", { sessionId: "s9" })).toEqual({ context: ["Keep this intent card verbatim"] })
    expect(calls[0].input.session).toBe("s9")
    const stop = { session_id: "s9", last_assistant_message: { role: "assistant", content: [{ type: "text", text: "Done." }] } }
    expect(await fire("session_stop", stop)).toEqual({ continue: true, additionalContext: "open items" })
    expect(calls[1].input).toMatchObject({ answer: "Done.", session: "s9" })
    // The continuation comes back through before_agent_start and must not reach the prompt hook.
    expect(await fire("before_agent_start", { prompt: "open items" })).toBeUndefined()
    expect(calls).toHaveLength(2)
  })

  it("records typed input as the user's words, never a synthetic prompt or an extension's", async () => {
    const { calls, fire } = await load("omp")
    // before_agent_start carries no authorship, so its prompt goes to the card hook unmarked.
    await fire("before_agent_start", { prompt: "Resume the user's latest intent." })
    expect(calls[0]).toEqual({ event: "prompt", input: { text: "Resume the user's latest intent.", cwd: "/repo", session: "s1" }, cwd: "/repo" })
    await fire("input", { text: "from an extension", source: "extension" })
    await fire("input", { text: "keep CSV", source: "interactive" }, "sub")
    expect(calls).toHaveLength(1)
    await fire("input", { text: "keep CSV via rpc", source: "rpc" })
    expect(calls.slice(1).map(({ event, input }) => [event, input.text])).toEqual([["user", "keep CSV via rpc"]])
  })
})
