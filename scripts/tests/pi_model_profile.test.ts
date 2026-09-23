// `/model-profile` extension contract: the CLI stays the only writer/validator, and every model
// switch this extension performs must come from a `,pi-model-profile --session <name>` row it
// parsed itself. These tests drive the registered command with a fake `pi`/`ctx`, so no chezmoi
// apply, no state file, and no provider call happens.

import { describe, expect, it } from "bun:test"
import register from "../../home/dot_pi/agent/exact_extensions/pi-model-profile.ts"

type ExecResult = { stdout: string; stderr: string; code: number; killed: boolean }
type Notice = { message: string; type: string }
type ExecStub = (args: string[]) => Partial<ExecResult>

const ok = (stdout: string): Partial<ExecResult> => ({ stdout })
const fail = (stderr: string, code = 1): Partial<ExecResult> => ({ stderr, code })

// Two names, `default` first, exactly as `--list` prints them.
const LIST = "default\nlocal\n"
const SHOW = "active pi model profile: local\n  session     llama-cpp/qwen3.8-27b (high)\n"

function harness(
  exec: ExecStub,
  options: { hasUI?: boolean; select?: (options: string[]) => string | undefined; catalogue?: string[]; auth?: boolean } = {},
) {
  const calls: Array<{ command: string; args: string[] }> = []
  const notices: Notice[] = []
  const models: Array<{ provider: string; modelId: string }> = []
  const levels: string[] = []
  let selectOptions: string[] = []
  const catalogue = options.catalogue ?? ["llama-cpp/qwen3.8-27b", "anthropic/claude-fable-5.1", "openrouter/z-ai/glm-5.3"]
  let handler: ((args: string, ctx: unknown) => Promise<void>) | undefined
  let completions: ((prefix: string) => Promise<unknown[] | null>) | undefined

  const pi = {
    registerCommand: (name: string, opts: Record<string, unknown>) => {
      expect(name).toBe("model-profile")
      handler = opts.handler as typeof handler
      completions = opts.getArgumentCompletions as typeof completions
    },
    exec: async (command: string, args: string[]) => {
      calls.push({ command, args })
      return { stdout: "", stderr: "", code: 0, killed: false, ...exec(args) } satisfies ExecResult
    },
    setModel: async (model: { provider: string; id: string }) => {
      if (options.auth === false) return false
      models.push({ provider: model.provider, modelId: model.id })
      return true
    },
    setThinkingLevel: (level: string) => levels.push(level),
  }
  register(pi as unknown as Parameters<typeof register>[0])

  const ctx = {
    hasUI: options.hasUI ?? true,
    modelRegistry: {
      find: (provider: string, modelId: string) =>
        catalogue.includes(`${provider}/${modelId}`) ? { provider, id: modelId } : undefined,
    },
    ui: {
      notify: (message: string, type = "info") => notices.push({ message, type }),
      select: async (_title: string, opts: string[]) => {
        selectOptions = opts
        return options.select ? options.select(opts) : opts[0]
      },
    },
  }

  return {
    run: (args = "") => handler!(args, ctx),
    complete: (prefix: string) => completions!(prefix),
    calls,
    notices,
    models,
    levels,
    get selectOptions() {
      return selectOptions
    },
  }
}

const listOnly: ExecStub = (args) => (args[0] === "--list" ? ok(LIST) : args[0] === "--show" ? ok(SHOW) : {})
const fullFlow =
  (sessionRow: string): ExecStub =>
  (args) => {
    if (args[0] === "--list") return ok(LIST)
    if (args[0] === "--show") return ok(SHOW)
    if (args[0] === "--session") return ok(sessionRow)
    return {}
  }

describe("WHEN /model-profile resolves the name to apply", () => {
  it("SHOULD select over the CLI's own list, marking only the active name", async () => {
    const runtime = harness(fullFlow("llama-cpp/qwen3.8-27b\thigh\n"))
    await runtime.run()
    expect(runtime.selectOptions).toEqual(["default", "local (active)"])
    expect(runtime.calls.map((call) => call.args)).toContainEqual(["default"])
  })

  it("SHOULD strip the active marker before handing the name back to the CLI", async () => {
    const runtime = harness(fullFlow("llama-cpp/qwen3.8-27b\thigh\n"), { select: (opts) => opts[1] })
    await runtime.run()
    expect(runtime.calls.map((call) => call.args)).toContainEqual(["local"])
    expect(runtime.calls.map((call) => call.args)).toContainEqual(["--session", "local"])
  })

  it("SHOULD pass an explicit argument through without listing or selecting", async () => {
    const runtime = harness(fullFlow("llama-cpp/qwen3.8-27b\thigh\n"))
    await runtime.run("  local  ")
    expect(runtime.calls[0]!.args).toEqual(["local"])
    expect(runtime.calls.some((call) => call.args[0] === "--list")).toBe(false)
  })

  it("SHOULD do nothing but notify on cancel, and nothing at all without dialog UI", async () => {
    const cancelled = harness(listOnly, { select: () => undefined })
    await cancelled.run()
    expect(cancelled.calls.some((call) => call.args.length === 1 && !call.args[0]!.startsWith("--"))).toBe(false)
    expect(cancelled.notices.at(-1)!.type).toBe("info")

    const headless = harness(listOnly, { hasUI: false })
    await headless.run()
    expect(headless.calls).toEqual([])
    expect(headless.notices).toEqual([])
  })

  it("SHOULD complete argument prefixes from the CLI list only", async () => {
    const runtime = harness(listOnly)
    expect(await runtime.complete("")).toEqual([
      { value: "default", label: "default" },
      { value: "local", label: "local" },
    ])
    expect(await runtime.complete("lo")).toEqual([{ value: "local", label: "local" }])
    expect(await runtime.complete("zz")).toBeNull()
    expect(runtime.calls.every((call) => call.args[0] === "--list")).toBe(true)
  })
})

describe("WHEN /model-profile maps a session row onto the live session", () => {
  it("SHOULD split the provider at the first slash, keeping multi-segment model ids intact", async () => {
    const runtime = harness(fullFlow("openrouter/z-ai/glm-5.3\txhigh\n"), { select: (opts) => opts[0] })
    await runtime.run()
    expect(runtime.models).toEqual([{ provider: "openrouter", modelId: "z-ai/glm-5.3" }])
    expect(runtime.levels).toEqual(["xhigh"])
    expect(runtime.notices.at(-1)!.type).toBe("info")
  })

  it("SHOULD warn without switching when the row is unusable, unknown, or unauthenticated", async () => {
    const cases: Array<[ExecStub, { auth?: boolean }]> = [
      [fullFlow("llama-cpp-qwen3.8-27b\thigh\n"), {}],
      [fullFlow("/qwen3.8-27b\thigh\n"), {}],
      [fullFlow("llama-cpp/\thigh\n"), {}],
      [fullFlow("llama-cpp/qwen3.8-27b\tturbo\n"), {}],
      [fullFlow("llama-cpp/qwen3.8-27b\n"), {}],
      [fullFlow("llama-cpp/not-in-catalogue\thigh\n"), {}],
      [fullFlow("llama-cpp/qwen3.8-27b\thigh\n"), { auth: false }],
      [(args) => (args[0] === "--session" ? fail("boom") : listOnly(args)), {}],
    ]
    for (const [exec, extra] of cases) {
      const runtime = harness(exec, { select: (opts) => opts[0], ...extra })
      await runtime.run()
      expect(runtime.models).toEqual([])
      expect(runtime.levels).toEqual([])
      const last = runtime.notices.at(-1)!
      expect(last.type).toBe("warning")
      expect(last.message).toContain("applied for new sessions")
    }
  })

  it("SHOULD never read a session row or switch a model when the apply itself failed", async () => {
    const runtime = harness((args) => (args[0] === "--list" || args[0] === "--show" ? listOnly(args) : fail("unknown pi model profile 'nope'")), {
      select: (opts) => opts[0],
    })
    await runtime.run()
    expect(runtime.calls.some((call) => call.args[0] === "--session")).toBe(false)
    expect(runtime.models).toEqual([])
    expect(runtime.levels).toEqual([])
    const last = runtime.notices.at(-1)!
    expect(last.type).toBe("error")
    expect(last.message).toContain("unknown pi model profile")
  })

  it("SHOULD report an unusable list as an error instead of applying an empty name", async () => {
    const runtime = harness((args) => (args[0] === "--list" ? ok("\n  \n") : {}))
    await runtime.run()
    expect(runtime.calls.map((call) => call.args)).toEqual([["--list"]])
    expect(runtime.notices.at(-1)!.type).toBe("error")
  })
})
