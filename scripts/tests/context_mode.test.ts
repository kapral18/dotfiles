import { afterAll, describe, expect, it } from "bun:test"
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join, resolve } from "node:path"
import { createContextMode } from "../../home/exact_lib/exact_shared/context_mode.ts"

const root = resolve(import.meta.dir, "../..")
const temp = mkdtempSync(join(tmpdir(), "context-mode-tests-"))
afterAll(() => rmSync(temp, { recursive: true, force: true }))
const adapters = [
  ["pi", "home/dot_pi/agent/exact_extensions/context-mode.ts.tmpl"],
  ["omp", "home/dot_omp/private_agent/extensions/context-mode.ts.tmpl"],
] as const
// Bun caches directory entries during import resolution. Materialize the whole
// fixture before the first import, as chezmoi does before runtime startup.
for (const [name, source] of adapters) {
  writeFileSync(join(temp, `${name}.ts`), readFileSync(join(root, source), "utf8").replace(
    "{{ .chezmoi.homeDir }}/lib/shared/context_mode.ts",
    join(root, "home/exact_lib/exact_shared/context_mode.ts"),
  ))
}

function model(id = "gpt-6-astra", provider = "openrouter", contextWindow = 1_000_000) {
  return {
    provider, id, contextWindow, maxTokens: 128_000, api: "openai-responses",
    cost: { input: 10 }, headers: { "x-fixture": "keep" },
  }
}
type Model = ReturnType<typeof model> & {
  maxContextWindow?: number
  cost: { input: number; longContext?: { inputThreshold: number }; tiers?: { inputTokensAbove: number }[] }
}
type Saved = { type: string; customType: string; data: unknown }

function harness(initial: Model = model()) {
  let current = initial
  let entries: Saved[] = []
  let tokens: number | null = 0
  let idle = true
  let failSelect = false
  let failAppend = false
  let changes = 0
  const catalog = new Map([[`${initial.provider}/${initial.id}`, initial]])
  const notices: string[] = []
  const statuses = new Map<string, string | undefined>()
  const ctx = {
    get model() { return current },
    modelRegistry: { find: (provider: string, id: string) => catalog.get(`${provider}/${id}`) },
    sessionManager: { getBranch: () => entries },
    getContextUsage: () => ({ tokens }),
    isIdle: () => idle,
    ui: {
      notify: (text: string) => { notices.push(text) },
      setStatus: (key: string, text: string | undefined) => { statuses.set(key, text) },
    },
  }
  let onSelect: (() => Promise<void>) | undefined
  const select = async (next: Model) => {
    if (failSelect) throw new Error("fixture auth failure")
    current = next
    changes++
    await onSelect?.()
  }
  const append = (customType: string, data: unknown) => {
    if (failAppend) throw new Error("fixture persistence failure")
    entries.push({ type: "custom", customType, data })
  }
  return {
    ctx, catalog, notices, statuses, select, append,
    policy: createContextMode(select, append),
    get current() { return current },
    get changes() { return changes },
    get entries() { return entries },
    set entries(value: Saved[]) { entries = value },
    set tokens(value: number | null) { tokens = value },
    set idle(value: boolean) { idle = value },
    set failSelect(value: boolean) { failSelect = value },
    set failAppend(value: boolean) { failAppend = value },
    set onSelect(value: () => Promise<void>) { onSelect = value },
    switch(next: Model) { current = next; catalog.set(`${next.provider}/${next.id}`, next) },
  }
}

describe("WHEN applying GPT-only defaults", () => {
  for (const [id, window] of [
    ["gpt-6-astra", 272_000], ["openai/gpt-6-astra", 272_000],
    ["claude-fable-5.1", 1_000_000], ["notgpt-6-astra", 1_000_000],
  ] as const) {
    it(`SHOULD give ${id} a ${window}-token window without mutating the catalog`, async () => {
      const original = model(id)
      const h = harness(original)
      await h.policy.apply(h.ctx)
      expect(h.current.contextWindow).toBe(window)
      expect(original.contextWindow).toBe(1_000_000)
      expect(h.entries).toEqual([])
      expect(h.current.maxTokens).toBe(128_000)
      expect(h.current.api).toBe("openai-responses")
      expect(h.current.headers).toBe(original.headers)
      expect(h.current.cost).toBe(original.cost)
    })
  }

  it("SHOULD respect smaller native windows and provider tier metadata", async () => {
    const small = harness(model("gpt-4o", "openai", 128_000))
    await small.policy.apply(small.ctx)
    expect(small.changes).toBe(0)
    const h = harness({ ...model(), cost: { input: 10, longContext: { inputThreshold: 200_000 } } })
    await h.policy.apply(h.ctx)
    expect(h.current.contextWindow).toBe(200_000)
  })

  it("SHOULD leave an unknown window unchanged", async () => {
    const h = harness(model("gpt-6-astra", "fixture", 0))
    await h.policy.command("long", h.ctx)
    expect(h.changes).toBe(0)
    expect(h.entries).toEqual([])
  })

  it("SHOULD use Pi's earliest valid input-price tier without changing cost metadata", async () => {
    const cost = { input: 0.2, tiers: [
      { inputTokensAbove: 400_000 }, { inputTokensAbove: 200_000 },
      { inputTokensAbove: 0 }, { inputTokensAbove: -1 }, { inputTokensAbove: NaN },
    ] }
    const h = harness({ ...model("gpt-5.6-luna"), cost })
    await h.policy.apply(h.ctx)
    expect(h.current.contextWindow).toBe(200_000)
    expect(h.current.cost).toBe(cost)
    await h.policy.command("long", h.ctx)
    expect(h.current.contextWindow).toBe(1_000_000)
  })

  it("SHOULD fall back only when neither native price-tier schema supplies a valid threshold", async () => {
    const h = harness({ ...model(), cost: { input: 10, tiers: [{ inputTokensAbove: Infinity }] } })
    await h.policy.apply(h.ctx)
    expect(h.current.contextWindow).toBe(272_000)
    h.switch({ ...model(), cost: {
      input: 10, longContext: { inputThreshold: 200_000 }, tiers: [{ inputTokensAbove: 128_000 }],
    } })
    await h.policy.apply(h.ctx)
    expect(h.current.contextWindow).toBe(128_000)
  })
})

describe("WHEN applying non-GPT dual windows", () => {
  it("SHOULD keep native Grok capacity until short is selected", async () => {
    const grok = {
      ...model("grok-4.5", "openrouter", 500_000),
      cost: { input: 4, tiers: [{ inputTokensAbove: 200_000 }] },
    }
    const h = harness(grok)
    await h.policy.apply(h.ctx)
    expect(h.current.contextWindow).toBe(500_000)
    expect(h.changes).toBe(0)
    expect(h.entries).toEqual([])
    await h.policy.command("short", h.ctx)
    expect(h.current.contextWindow).toBe(200_000)
    expect(h.entries).toEqual([{
      type: "custom", customType: "gpt-context-mode",
      data: { provider: "openrouter", model: "grok-4.5", mode: "short" },
    }])
    await h.policy.command("long", h.ctx)
    expect(h.current.contextWindow).toBe(500_000)
  })

  it("SHOULD refuse short when Grok history already exceeds the 200k tier", async () => {
    const grok = {
      ...model("grok-4.6", "openrouter", 500_000),
      cost: { input: 4, tiers: [{ inputTokensAbove: 200_000 }] },
    }
    const h = harness(grok)
    h.tokens = 200_000
    await h.policy.command("short", h.ctx)
    expect(h.current.contextWindow).toBe(500_000)
    expect(h.entries).toEqual([])
    expect(h.notices.at(-1)).toContain("Mode unchanged")
  })

  it("SHOULD use advertised maxContextWindow as long for non-GPT without mutating on apply", async () => {
    const h = harness({
      ...model("claude-opus-5", "anthropic", 200_000),
      maxContextWindow: 1_000_000,
    })
    await h.policy.apply(h.ctx)
    expect(h.current.contextWindow).toBe(200_000)
    expect(h.changes).toBe(0)
    await h.policy.command("long", h.ctx)
    expect(h.current.contextWindow).toBe(1_000_000)
    await h.policy.command("short", h.ctx)
    expect(h.current.contextWindow).toBe(200_000)
  })
})

describe("WHEN selecting and restoring a model/session context mode", () => {
  it("SHOULD round-trip short/long without changing provider, model, output or cache metadata", async () => {
    const h = harness()
    await h.policy.apply(h.ctx)
    await h.policy.command("long", h.ctx)
    expect(h.current.contextWindow).toBe(1_000_000)
    expect(h.entries).toEqual([{
      type: "custom", customType: "gpt-context-mode",
      data: { provider: "openrouter", model: "gpt-6-astra", mode: "long" },
    }])
    await h.policy.command("short", h.ctx)
    expect(h.current.contextWindow).toBe(272_000)
    expect(h.current.provider).toBe("openrouter")
    expect(h.current.id).toBe("gpt-6-astra")
    expect(h.current.maxTokens).toBe(128_000)
  })

  it("SHOULD restore per-provider and per-model selections without leaking into another session", async () => {
    const h = harness()
    await h.policy.command("long", h.ctx)
    // Same model id on a second provider: the saved `long` entry is keyed by provider *and*
    // model, so it must not restore here. Keep this provider different from `model()`'s
    // default, or the case stops probing the leak it is named for.
    h.switch(model("gpt-6-astra", "anthropic"))
    await h.policy.apply(h.ctx)
    expect(h.current.contextWindow).toBe(272_000)
    h.switch(model("gpt-5.6-sol"))
    await h.policy.apply(h.ctx)
    expect(h.current.contextWindow).toBe(272_000)
    h.switch(model("claude-fable-5.1"))
    await h.policy.apply(h.ctx)
    expect(h.current.contextWindow).toBe(1_000_000)
    h.switch(model())
    await createContextMode(h.select, h.append).apply(h.ctx)
    expect(h.current.contextWindow).toBe(1_000_000)
    h.entries = []
    await h.policy.apply(h.ctx)
    expect(h.current.contextWindow).toBe(272_000)
  })

  it("SHOULD use refreshed native metadata and a known advertised maximum for long mode", async () => {
    const h = harness()
    await h.policy.command("long", h.ctx)
    h.switch({ ...model(), contextWindow: 272_000, maxContextWindow: 922_000 })
    await h.policy.apply(h.ctx)
    expect(h.current.contextWindow).toBe(922_000)
    h.catalog.clear()
    await h.policy.command("short", h.ctx)
    await h.policy.command("long", h.ctx)
    expect(h.current.contextWindow).toBe(922_000)
  })

  it("SHOULD ignore malformed or foreign entries and use only the active branch", async () => {
    const h = harness()
    h.entries = [
      { type: "custom", customType: "gpt-context-mode", data: null },
      { type: "custom", customType: "gpt-context-mode", data: { provider: "other", model: "gpt-6-astra", mode: "long" } },
      { type: "custom", customType: "other", data: { provider: "openrouter", model: "gpt-6-astra", mode: "long" } },
      { type: "custom", customType: "gpt-context-mode", data: { provider: "openrouter", model: "gpt-6-astra", mode: "invalid" } },
    ]
    await h.policy.apply(h.ctx)
    expect(h.current.contextWindow).toBe(272_000)
  })
})

describe("WHEN a selection must not proceed", () => {
  it("SHOULD reject invalid args, busy turns, and non-GPT changes without saving", async () => {
    const h = harness()
    await h.policy.command("long extra", h.ctx)
    h.idle = false
    await h.policy.command("long", h.ctx)
    h.idle = true
    h.switch(model("claude-fable-5.1"))
    await h.policy.command("short", h.ctx)
    expect(h.changes).toBe(0)
    expect(h.entries).toEqual([])
  })

  it("SHOULD retain long mode for oversized history, without invoking compaction", async () => {
    const h = harness()
    await h.policy.command("long", h.ctx)
    h.tokens = 272_000
    await h.policy.command("short", h.ctx)
    expect(h.current.contextWindow).toBe(1_000_000)
    expect(h.entries).toHaveLength(1)
    expect(h.notices.at(-1)).toContain("Mode unchanged")
    h.tokens = 50_000
    await h.policy.command("short", h.ctx)
    expect(h.current.contextWindow).toBe(272_000)
  })

  it("SHOULD not save failed selections or recurse through native model_select", async () => {
    const h = harness()
    h.failSelect = true
    await h.policy.command("short", h.ctx)
    expect(h.entries).toEqual([])
    expect(h.current.contextWindow).toBe(1_000_000)
    h.failSelect = false
    h.onSelect = async () => { await h.policy.apply(h.ctx) }
    await h.policy.command("short", h.ctx)
    expect(h.changes).toBe(1)
    expect(h.entries).toHaveLength(1)
    await h.policy.command("status", h.ctx)
    expect(h.entries).toHaveLength(1)
  })

  it("SHOULD restore active metadata when persistence fails", async () => {
    const h = harness()
    await h.policy.apply(h.ctx)
    h.failAppend = true
    await h.policy.command("long", h.ctx)
    expect(h.current.contextWindow).toBe(272_000)
    expect(h.entries).toEqual([])
    expect(h.notices.at(-1)).toContain("fixture persistence failure")
  })

  it("SHOULD reject another selection while the native model change is pending", async () => {
    const h = harness()
    let release!: () => void
    let entered!: () => void
    const gate = new Promise<void>((resolve) => { release = resolve })
    const started = new Promise<void>((resolve) => { entered = resolve })
    h.onSelect = async () => { entered(); await gate }
    const pending = h.policy.command("short", h.ctx)
    await started
    await h.policy.command("long", h.ctx)
    expect(h.entries).toEqual([])
    expect(h.notices.at(-1)).toContain("Wait")
    release()
    await pending
    expect(h.current.contextWindow).toBe(272_000)
    expect(h.entries).toHaveLength(1)
  })
})

describe("WHEN the native active branch grows", () => {
  for (const count of [0, 1, 1000, 10_000]) {
    it(`SHOULD restore the same model selection across ${count} unrelated entries`, async () => {
      const h = harness()
      await h.policy.command("long", h.ctx)
      h.entries.push(...Array.from({ length: count }, () => ({
        type: "custom", customType: "other", data: null,
      })))
      h.switch(model())
      await h.policy.apply(h.ctx)
      expect(h.current.contextWindow).toBe(1_000_000)
      expect(h.entries).toHaveLength(count + 1)
    })
  }
})

async function loadAdapter(name: "pi" | "omp") {
  const h = harness()
  const timers: (() => Promise<void>)[] = []
  const waiters = new Set<() => void>()
  const discoveryWork: Promise<void>[] = []
  let discovered = false
  let effort = "high"
  let beforeSelect = async () => {}
  const ctx = {
    ...h.ctx,
    get model() { return h.current },
    modelRegistry: {
      ...h.ctx.modelRegistry,
      awaitInitialBackgroundRefresh(signal?: AbortSignal) {
        if (discovered || signal?.aborted) return Promise.resolve()
        const { promise, resolve } = Promise.withResolvers<void>()
        const settle = () => {
          signal?.removeEventListener("abort", settle)
          waiters.delete(settle)
          resolve()
        }
        waiters.add(settle)
        signal?.addEventListener("abort", settle, { once: true })
        discoveryWork.push(promise)
        return promise
      },
    },
    setTimeout: (callback: () => Promise<void>) => { timers.push(callback) },
  }
  type HandlerResult = void | { cancel: boolean }
  const handlers = new Map<string, (_: unknown, context: typeof ctx) => HandlerResult | Promise<HandlerResult>>()
  let command: { handler: typeof h.policy.command; getArgumentCompletions: (prefix: string) => unknown } | undefined
  // The rendered module path is created at runtime, so a static import cannot load it.
  const { default: register } = await import(join(temp, `${name}.ts`))
  register({
    setModel: async (next: Model) => { await beforeSelect(); await h.select(next); effort = "low"; return true },
    getThinkingLevel: () => effort,
    setThinkingLevel: (value: string) => { effort = value },
    appendEntry: h.append,
    on: (event: string, handler: (_: unknown, context: typeof ctx) => HandlerResult | Promise<HandlerResult>) => handlers.set(event, handler),
    registerCommand: (_name: string, value: NonNullable<typeof command>) => { command = value },
  })
  return {
    h,
    set beforeSelect(callback: () => Promise<void>) { beforeSelect = callback },
    get effort() { return effort },
    emit: (event: string) => handlers.get(event)?.({}, ctx),
    command: (args: string) => command!.handler(args, ctx),
    complete: (prefix: string) => command!.getArgumentCompletions(prefix),
    flushTimers: () => Promise.all(timers.splice(0).map(callback => callback())),
    async finishDiscovery() {
      discovered = true
      for (const settle of waiters) settle()
      await Promise.all(discoveryWork)
    },
  }
}

for (const [name] of adapters) {
  describe(`WHEN ${name} changes the working context window`, () => {
    it("SHOULD preserve explicit effort through short and long mode", async () => {
      const adapter = await loadAdapter(name)
      await adapter.emit("session_start")
      expect(adapter.h.current.contextWindow).toBe(272_000)
      expect(adapter.effort).toBe("high")
      await adapter.command("long")
      expect(adapter.h.current.contextWindow).toBe(1_000_000)
      expect(adapter.effort).toBe("high")
    })
  })
  describe(`WHEN ${name} completes a context-mode prefix`, () => {
    it("SHOULD offer matching commands and exclude nonmatching commands", async () => {
      const adapter = await loadAdapter(name)
      expect(adapter.complete("s")).toEqual([
        { value: "short", label: "short" }, { value: "status", label: "status" },
      ])
    })
  })
}

describe("WHEN OMP finishes deferred model discovery", () => {
  it("SHOULD restore short mode without blocking startup or mutating the catalog", async () => {
    const adapter = await loadAdapter("omp")
    await adapter.emit("session_start")
    const refreshed = model("gpt-6-astra", "openrouter", 922_000)
    adapter.h.switch(refreshed)

    await adapter.finishDiscovery()
    await adapter.flushTimers()

    expect(adapter.h.current.contextWindow).toBe(272_000)
    expect(refreshed.contextWindow).toBe(922_000)
    expect(adapter.h.current.id).toBe("gpt-6-astra")
    expect(adapter.effort).toBe("high")
  })

  it("SHOULD keep a long-mode choice made before discovery finishes", async () => {
    const adapter = await loadAdapter("omp")
    await adapter.emit("session_start")
    await adapter.command("long")
    adapter.h.switch(model("gpt-6-astra", "openrouter", 922_000))

    await adapter.finishDiscovery()
    await adapter.flushTimers()

    expect(adapter.h.current.contextWindow).toBe(922_000)
    expect(adapter.h.entries.at(-1)?.data).toEqual({
      provider: "openrouter", model: "gpt-6-astra", mode: "long",
    })
  })

  it("SHOULD use the current model rather than restoring the startup model", async () => {
    const adapter = await loadAdapter("omp")
    await adapter.emit("session_start")
    adapter.h.switch(model("claude-fable-5.1", "anthropic", 500_000))

    await adapter.finishDiscovery()
    await adapter.flushTimers()

    expect(adapter.h.current.id).toBe("claude-fable-5.1")
    expect(adapter.h.current.contextWindow).toBe(500_000)
  })

  it("SHOULD leave a closed session unchanged when discovery finishes", async () => {
    const adapter = await loadAdapter("omp")
    await adapter.emit("session_start")
    const background = adapter.flushTimers()
    await adapter.emit("session_shutdown")
    adapter.h.switch(model("gpt-6-astra", "openrouter", 922_000))

    await adapter.finishDiscovery()
    await background

    expect(adapter.h.current.contextWindow).toBe(922_000)
  })

  it("SHOULD wait for an overlapping short-mode command to finish saving", async () => {
    const adapter = await loadAdapter("omp")
    await adapter.emit("session_start")
    await adapter.command("long")
    const background = adapter.flushTimers()
    const entered = Promise.withResolvers<void>()
    const release = Promise.withResolvers<void>()
    adapter.h.onSelect = async () => { entered.resolve(); await release.promise }
    const command = adapter.command("short")
    await entered.promise
    adapter.h.switch(model("gpt-6-astra", "openrouter", 922_000))

    await adapter.finishDiscovery()
    release.resolve()
    await command
    await background

    expect(adapter.h.current.contextWindow).toBe(272_000)
    expect(adapter.h.entries.at(-1)?.data).toEqual({
      provider: "openrouter", model: "gpt-6-astra", mode: "short",
    })
  })

  it.each(["session_before_switch", "session_before_branch", "session_before_tree"])(
    "SHOULD refuse %s synchronously while a correction is awaiting authentication",
    async (event) => {
      const adapter = await loadAdapter("omp")
      await adapter.emit("session_start")
      const background = adapter.flushTimers()
      const entered = Promise.withResolvers<void>()
      const release = Promise.withResolvers<void>()
      adapter.beforeSelect = async () => { entered.resolve(); await release.promise }
      adapter.h.switch(model("gpt-6-astra", "openrouter", 922_000))
      await adapter.finishDiscovery()
      await entered.promise

      // A synchronous cancel cannot be lost to the native async-handler timeout.
      const blocked = adapter.emit(event)
      release.resolve()
      await background

      expect(blocked).toEqual({ cancel: true })
      expect(adapter.emit(event)).toBeUndefined()
      expect(adapter.h.current.contextWindow).toBe(272_000)
      expect(adapter.h.current.id).toBe("gpt-6-astra")
    },
  )

  it("SHOULD refuse a transition until queued discovery work has finished", async () => {
    const adapter = await loadAdapter("omp")
    await adapter.emit("session_start")

    const blocked = adapter.emit("session_before_switch")
    await adapter.finishDiscovery()
    await adapter.flushTimers()

    expect(blocked).toEqual({ cancel: true })
    expect(adapter.emit("session_before_switch")).toBeUndefined()
    expect(adapter.h.current.contextWindow).toBe(272_000)
  })
})
