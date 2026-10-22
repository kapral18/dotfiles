import { afterAll, describe, expect, it, mock } from "bun:test"
import { chmodSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs"
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
  opencode: "home/dot_config/opencode/plugins/readonly_intent-guard.ts.tmpl",
} as const
// OpenCode's host provides `@opencode/plugin`; the test stands in for it.
mock.module("@opencode/plugin", () => ({ Plugin: { define: (plugin: unknown) => plugin } }))
// Materialize every adapter before the first import, as chezmoi does before runtime startup.
for (const [name, source] of Object.entries(adapters)) {
  writeFileSync(join(temp, `${name}.ts`), readFileSync(join(root, source), "utf8").replace(
    "{{ .chezmoi.homeDir }}/lib/shared/intent_guard.ts",
    join(root, "home/exact_lib/exact_shared/intent_guard.ts"),
  ))
}

type Handler = (event: any, ctx: any) => Promise<any>

// A fake host: `,task hook <event>` answers from `answers`; every call is recorded.
async function load(name: "pi" | "omp", answers: Record<string, unknown> = {}) {
  const handlers = new Map<string, Handler>()
  const calls: { event: string; input: Record<string, unknown>; cwd?: string }[] = []
  const messages: unknown[] = []
  const pi = {
    on: (event: string, handler: Handler) => { handlers.set(event, handler) },
    sendMessage: (message: unknown, options: unknown) => { messages.push({ message, options }) },
    exec: async (command: string, args: string[], options?: { cwd?: string }) => {
      expect(command).toBe(",task")
      calls.push({ event: args[1], input: JSON.parse(args[5]), cwd: options?.cwd })
      return { stdout: JSON.stringify(answers[args[1]] ?? {}), stderr: "", code: 0, killed: false }
    },
  }
  const module = await import(join(temp, `${name}.ts`))
  module.default(pi)
  const ctx = { cwd: "/repo", sessionManager: { getSessionId: () => "s1" }, agent: { kind: "main" } }
  const fire = (event: string, payload: unknown, agent = "main") => handlers.get(event)!(payload, { ...ctx, agent: { kind: agent } })
  return { calls, fire, handlers, messages }
}

describe("shared intent guard", () => {
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
})

describe("pi adapter", () => {
  it("adds the card to a typed prompt only", async () => {
    const { calls, fire } = await load("pi", { prompt: { context: "Intent card for this task" } })
    const result = await fire("before_agent_start", { messageType: "user", prompt: "add the button" })
    expect(result).toEqual({ message: { customType: "intent-guard", content: "Intent card for this task", display: false } })
    expect(calls[0]).toEqual({ event: "prompt", input: { text: "add the button", cwd: "/repo", session: "s1" }, cwd: "/repo" })
    expect(await fire("before_agent_start", { messageType: "custom", message: {} })).toBeUndefined()
  })

  it("records typed input as the user's words and nothing an extension sends", async () => {
    const { calls, fire } = await load("pi")
    expect(await fire("input", { text: "from an extension", source: "extension" })).toBeUndefined()
    expect(calls).toEqual([])
    for (const source of ["interactive", "rpc"]) await fire("input", { text: `keep CSV via ${source}`, source })
    expect(calls.map(({ event, input }) => [event, input.text])).toEqual([["user", "keep CSV via interactive"], ["user", "keep CSV via rpc"]])
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
    for (const source of ["interactive", "rpc"]) await fire("input", { text: `keep CSV via ${source}`, source })
    expect(calls.slice(1).map(({ event, input }) => [event, input.text])).toEqual([["user", "keep CSV via interactive"], ["user", "keep CSV via rpc"]])
  })
})

describe("opencode adapter", () => {
  // A fake `~/bin/,task` that logs its arguments and answers from a JSON map keyed by event.
  function fakeTask(answers: Record<string, unknown>) {
    const home = mkdtempSync(join(temp, "home-"))
    mkdirSync(join(home, "bin"))
    writeFileSync(join(home, "answers.json"), JSON.stringify(answers))
    const script = join(home, "bin", ",task")
    writeFileSync(script, `#!/bin/sh\nprintf '%s\\n' "$*" >> "${home}/calls.log"\npython3 -c 'import json,sys; print(json.dumps(json.load(open(sys.argv[1])).get(sys.argv[2], {})))' "${home}/answers.json" "$2"\n`)
    chmodSync(script, 0o755)
    return home
  }

  async function setup(answers: Record<string, unknown>) {
    const home = fakeTask(answers)
    process.env.HOME = home
    const hooks = new Map<string, (event: any) => Promise<void> | void>()
    const prompts: unknown[] = []
    let push: ((event: unknown) => void) | undefined
    const events = (async function* () {
      while (true) yield await new Promise((resolve) => { push = resolve })
    })()
    const ctx = {
      location: { directory: home },
      session: {
        hook: async (name: string, cb: any) => { hooks.set(`session.${name}`, cb) },
        prompt: async (input: unknown) => { prompts.push(input) },
        get: async ({ sessionID }: { sessionID: string }) => (sessionID === "child" ? { parentID: "s1" } : {}),
      },
      tool: { hook: async (name: string, cb: any) => { hooks.set(`tool.${name}`, cb) } },
      event: { subscribe: () => events },
    }
    const module = await import(join(temp, "opencode.ts"))
    const cleanup = await module.default.setup(ctx)
    const calls = () => readFileSync(join(home, "calls.log"), "utf8").trim().split("\n")
    return { hooks, prompts, calls, cleanup, emit: (event: unknown) => push?.(event) }
  }

  it("pins the card on each request and refuses an uncarded edit", async () => {
    const { hooks, calls } = await setup({ prompt: { context: "Intent card" }, tool: { deny: "no intent card" } })
    await hooks.get("session.prompt")!({ sessionID: "s1", prompt: { text: "add it" } })
    const request = { sessionID: "s1", system: [] as unknown[] }
    await hooks.get("session.context")!(request)
    expect(request.system).toEqual([{ type: "text", text: "Intent card" }])
    await expect(hooks.get("tool.execute.before")!({ tool: "edit", sessionID: "s1", input: { path: "src/a.ts" } })).rejects.toThrow("no intent card")
    expect(calls()[0]).toContain("hook prompt --harness opencode --input")
    // A command's expanded template reaches this hook too, so the text is never marked as the user's words.
    expect(calls()[0]).not.toContain('"origin"')
  })

  it("appends the note to the tool result and follows up a run with open items", async () => {
    const { hooks, prompts, emit, cleanup } = await setup({ tool: { note: "zoom out" }, stop: { block: "open items" } })
    const event = { tool: "shell", sessionID: "s1", status: "completed", input: {}, result: { content: "out" } }
    await hooks.get("tool.execute.after")!(event)
    expect(event.result.content).toEqual([{ type: "text", text: "out" }, { type: "text", text: "zoom out" }])

    await Bun.sleep(10)
    emit({ type: "session.execution.succeeded", data: { sessionID: "s1" } })
    for (let i = 0; i < 100 && prompts.length === 0; i++) await Bun.sleep(10)
    expect(prompts).toEqual([{ sessionID: "s1", text: "open items", metadata: { intentGuardFollowUp: true } }])
    await cleanup()
  })

  it("leaves a subagent's child session alone", async () => {
    const { hooks, calls } = await setup({ tool: { deny: "no intent card" } })
    await hooks.get("tool.execute.before")!({ tool: "edit", sessionID: "child", input: { path: "src/a.ts" } })
    expect(() => calls()).toThrow()
  })

  it("pairs shell errors with the before snapshot but does not mark failed direct edits", async () => {
    const { hooks, calls, cleanup } = await setup({})
    const shell = { tool: "shell", sessionID: "s1", id: "shell-42", input: {} }
    await hooks.get("tool.execute.before")!(shell)
    await hooks.get("tool.execute.after")!({ ...shell, status: "error", error: "exit 1" })
    await hooks.get("tool.execute.after")!({ tool: "edit", sessionID: "s1", id: "edit-43", status: "error", input: { path: "src/a.ts" } })
    const payloads = calls().map((line) => JSON.parse(line.split(" --input ")[1]))
    expect(payloads.map((input) => [input.call_id, input.phase])).toEqual([["shell-42", "before"], ["shell-42", "after"]])
    await cleanup()
  })
})
