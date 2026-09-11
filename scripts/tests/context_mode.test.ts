import { afterAll, describe, expect, it } from "bun:test"
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join, resolve } from "node:path"
import { createContextMode } from "../../home/exact_lib/exact_shared/context_mode.ts"

const root = resolve(import.meta.dir, "../..")
const temp = mkdtempSync(join(tmpdir(), "context-mode-tests-"))
afterAll(() => rmSync(temp, { recursive: true, force: true }))
const adapters = [
  ["pi", "home/dot_pi/agent/exact_extensions/context-mode.ts.tmpl", ["session_start", "session_tree", "model_select", "before_agent_start"]],
  ["omp", "home/dot_omp/private_agent/extensions/context-mode.ts.tmpl", ["session_start", "session_switch", "session_tree", "before_agent_start"]],
] as const
// Bun caches directory entries during import resolution. Materialize the whole
// fixture before the first import, as chezmoi does before runtime startup.
for (const [name, source] of adapters) {
  writeFileSync(join(temp, `${name}.ts`), readFileSync(join(root, source), "utf8").replace(
    "{{ .chezmoi.homeDir }}/lib/shared/context_mode.ts",
    join(root, "home/exact_lib/exact_shared/context_mode.ts"),
  ))
}

function model(id = "gpt-6-astra", provider = "github-copilot", contextWindow = 1_000_000) {
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

describe("WHEN selecting and restoring a model/session context mode", () => {
  it("SHOULD round-trip short/long without changing provider, model, output or cache metadata", async () => {
    const h = harness()
    await h.policy.apply(h.ctx)
    await h.policy.command("long", h.ctx)
    expect(h.current.contextWindow).toBe(1_000_000)
    expect(h.entries).toEqual([{
      type: "custom", customType: "gpt-context-mode",
      data: { provider: "github-copilot", model: "gpt-6-astra", mode: "long" },
    }])
    await h.policy.command("short", h.ctx)
    expect(h.current.contextWindow).toBe(272_000)
    expect(h.current.provider).toBe("github-copilot")
    expect(h.current.id).toBe("gpt-6-astra")
    expect(h.current.maxTokens).toBe(128_000)
  })

  it("SHOULD restore per-provider and per-model selections without leaking into another session", async () => {
    const h = harness()
    await h.policy.command("long", h.ctx)
    h.switch(model("gpt-6-astra", "openrouter"))
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
      { type: "custom", customType: "other", data: { provider: "github-copilot", model: "gpt-6-astra", mode: "long" } },
      { type: "custom", customType: "gpt-context-mode", data: { provider: "github-copilot", model: "gpt-6-astra", mode: "invalid" } },
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

for (const [name, _source, expectedEvents] of adapters) {
  describe(`WHEN ${name} loads the rendered extension`, () => {
    it("SHOULD wire native lifecycle events and preserve explicit effort", async () => {
      const h = harness()
      const handlers = new Map<string, (_: unknown, ctx: typeof h.ctx) => Promise<void>>()
      let command: { handler: typeof h.policy.command; getArgumentCompletions: (prefix: string) => unknown } | undefined
      let effort = "high"
      const api = {
        setModel: async (next: Model) => { await h.select(next); effort = "low"; return true },
        getThinkingLevel: () => effort,
        setThinkingLevel: (value: string) => { effort = value },
        appendEntry: h.append,
        on: (event: string, handler: (_: unknown, ctx: typeof h.ctx) => Promise<void>) => handlers.set(event, handler),
        registerCommand: (name: string, value: NonNullable<typeof command>) => {
          expect(name).toBe("context-mode")
          command = value
        },
      }
      const path = join(temp, `${name}.ts`)
      const { default: register } = await import(path)
      register(api)
      expect([...handlers.keys()]).toEqual(expectedEvents)
      await handlers.get("session_start")!({}, h.ctx)
      expect(h.current.contextWindow).toBe(272_000)
      expect(effort).toBe("high")
      await command!.handler("long", h.ctx)
      expect(h.current.contextWindow).toBe(1_000_000)
      expect(effort).toBe("high")
      expect(command!.getArgumentCompletions("s")).toEqual([
        { value: "short", label: "short" }, { value: "status", label: "status" },
      ])
    })
  })
}
