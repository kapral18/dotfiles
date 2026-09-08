import { afterAll, describe, expect, it } from "bun:test"
import { existsSync, mkdirSync, mkdtempSync, readFileSync, realpathSync, rmSync, statSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import register from "../../home/dot_omp/private_agent/extensions/runtime-parity.ts"

const fixtureDir = mkdtempSync(join(tmpdir(), "omp-terminal-test-"))
const agentDir = realpathSync(fixtureDir)
mkdirSync(join(agentDir, "agents"))
const profilePath = join(agentDir, "agents", "task.md")
writeFileSync(profilePath, "managed profile sentinel\n")
type Profile = Partial<Awaited<ReturnType<Parameters<typeof register>[0]["pi"]["discoverAgents"]>>["agents"][number]> & { name: string }
const managedProfile = {
  name: "task", source: "user", filePath: profilePath, systemPrompt: "[DELEGATION BOUNDARY]",
  blocking: true, tools: ["read", "bash", "edit", "yield"], model: ["@task"],
} satisfies Profile
let fixtureId = 0
afterAll(() => rmSync(fixtureDir, { recursive: true, force: true }))

function harness(values: Record<string, unknown> | undefined, initialTools: string[] = [], sessionFile: string | null = join(fixtureDir, `${++fixtureId}.jsonl`), options: { profiles?: Profile[]; reload?: () => Promise<void>; discoveryError?: boolean } = {}) {
  type Call = { toolName: string; input: Record<string, unknown> }
  type Context = { cwd: string; abort: () => void; sessionManager: { getSessionFile: () => string | null } }
  type Decision = { block: boolean; reason: string } | undefined
  type Handler = (event: Call, ctx: Context) => Decision | Promise<Decision>
  type PromptHandler = (event: { systemPrompt: string[] }, ctx: Context) => { systemPrompt: string[] } | undefined
  type ResultHandler = (event: { toolName: string; content: unknown[] }) => { content: unknown[]; isError: boolean } | undefined
  const handlers = new Map<string, unknown>()
  const events = new Map<string, (data: unknown) => void>()
  let tools = initialTools
  let aborts = 0
  if (sessionFile && !existsSync(sessionFile)) writeFileSync(sessionFile, "transcript sentinel\n")
  const ctx = { cwd: agentDir, abort: () => { aborts++ }, sessionManager: { getSessionFile: () => sessionFile } }
  const settings = values && { get: (key: string) => values[key], reloadFromDisk: options.reload ?? (async () => {}) }
  register({
    pi: {
      Settings: { get instance() { if (!settings) throw new Error("unavailable"); return settings } },
      getAgentDir: () => agentDir,
      discoverAgents: async () => {
        if (options.discoveryError) throw new Error("discovery unavailable")
        return { agents: options.profiles ?? [managedProfile] }
      },
    },
    on: (name: string, handler: unknown) => handlers.set(name, handler),
    events: { on: (name: string, handler: (data: unknown) => void) => events.set(name, handler) },
    getAllTools: () => tools.map((name) => ({ name })),
  } as unknown as Parameters<typeof register>[0])
  return {
    call: async (toolName: string, input: Record<string, unknown> = {}) => (handlers.get("tool_call") as Handler)({ toolName, input }, ctx),
    start: (systemPrompt: string[]) => (handlers.get("before_agent_start") as PromptHandler)({ systemPrompt }, ctx),
    result: (toolName: string) => (handlers.get("tool_result") as ResultHandler)({ toolName, content: [] }),
    provider: () => (handlers.get("before_provider_request") as (event: unknown, ctx: Context) => void)({}, ctx),
    lifecycle: (data: unknown) => events.get("task:subagent:lifecycle")!(data),
    sessionFile,
    get aborts() { return aborts },
    tools: (next: string[]) => { tools = next },
  }
}

const foreground = { "bash.autoBackground.enabled": false, "eval.autoBackground.enabled": false }

describe("WHEN OMP CLI dispatch inherits effective root settings", () => {
  it.each(["bash.autoBackground.enabled", "eval.autoBackground.enabled"])("SHOULD reject %s overrides before task or Eval dispatch", async (key) => {
    const values = { ...foreground, [key]: true }
    const runtime = harness(values)
    for (const tool of ["task", "eval"]) {
      const result = (await runtime.call(tool, { async: true }))!
      expect(result.block).toBe(true)
      expect(result.reason).toContain(key)
    }
    expect(values[key as keyof typeof values]).toBe(true)
    expect(await runtime.call("bash", { command: "read-only root work" })).toBeUndefined()
  })

  it("SHOULD preserve explicit root async and ordinary tools under foreground defaults", async () => {
    const runtime = harness(foreground)
    expect(await runtime.call("task", { agent: "task", async: true, effort: "hi" })).toBeUndefined()
    expect(await runtime.call("eval", { async: true })).toBeUndefined()
    expect(await runtime.call("bash", { async: true })).toBeUndefined()
    expect(await runtime.call("hub", { op: "send", name: "server", text: "status" })).toBeUndefined()
  })

  it("SHOULD reject unavailable or incomplete settings without blocking unrelated root work", async () => {
    for (const settings of [undefined, {}, { ...foreground, "eval.autoBackground.enabled": undefined }]) {
      const runtime = harness(settings)
      expect((await runtime.call("task"))?.block).toBe(true)
      expect((await runtime.call("eval"))?.block).toBe(true)
      expect(await runtime.call("read", { path: "README.md" })).toBeUndefined()
    }
  })

  it("SHOULD inspect changed effective values on each dispatch, without changing either settings object", async () => {
    const unsafe = { ...foreground, "bash.autoBackground.enabled": true }
    const safe = { ...foreground }
    const unsafeRuntime = harness(unsafe)
    const safeRuntime = harness(safe)
    expect((await unsafeRuntime.call("task"))?.block).toBe(true)
    expect(await safeRuntime.call("task", { agent: "task" })).toBeUndefined()
    unsafe["bash.autoBackground.enabled"] = false
    expect(await unsafeRuntime.call("task", { agent: "task" })).toBeUndefined()
    expect(safe).toEqual(foreground)
  })

  it("SHOULD reload disk layers before admitting dispatch and reject reload failures", async () => {
    const values = { ...foreground }
    const runtime = harness(values, [], undefined, { reload: async () => { values["eval.autoBackground.enabled"] = true } })
    expect((await runtime.call("task", { agent: "task" }))?.reason).toContain("eval.autoBackground.enabled")
    const broken = harness(foreground, [], undefined, { reload: async () => { throw new Error("unreadable") } })
    expect((await broken.call("task", { agent: "task" }))?.reason).toContain("Cannot establish OMP CLI foreground settings")
  })
})

describe("WHEN OMP resolves effective worker profiles", () => {
  it("SHOULD admit explicit managed profiles in flat and batch packets without rewriting them", async () => {
    const runtime = harness(foreground)
    const input = { tasks: [{ agent: "task", task: "produce artifact" }, { agent: "task", task: "independent artifact" }], async: true, effort: "hi" }
    const before = structuredClone(input)
    expect(await runtime.call("task", input)).toBeUndefined()
    expect(input).toEqual(before)
  })

  it("SHOULD reject implicit defaults and malformed or partially unnamed batches", async () => {
    const runtime = harness(foreground)
    for (const input of [{}, { agent: "" }, { agent: "../task" }, { tasks: [] }, { tasks: [null] }, { tasks: [{ agent: "task" }, {}] }]) {
      expect((await runtime.call("task", input))?.reason).toContain("explicit managed profile names")
    }
  })

  it("SHOULD reject project, plugin-path and bundled replacements even with a leaf marker", async () => {
    const outside = join(agentDir, "plugin.md")
    writeFileSync(outside, "plugin sentinel\n")
    const replacements: Profile[] = [{ ...managedProfile, source: "project" }, { ...managedProfile, filePath: outside }, { ...managedProfile, source: "bundled", filePath: undefined }]
    for (const profile of replacements) {
      const runtime = harness(foreground, [], undefined, { profiles: [profile] })
      expect((await runtime.call("task", { agent: "task" }))?.reason).toContain("not the enabled managed user profile")
    }
  })

  it("SHOULD reject profiles missing foreground, leaf, tool or explicit model controls", async () => {
    const unsafe: Profile[] = [
      { ...managedProfile, blocking: false }, { ...managedProfile, spawns: "*" },
      { ...managedProfile, advisor: "@advisor" }, { ...managedProfile, prewalk: "@plan" },
      { ...managedProfile, tools: [] }, { ...managedProfile, model: undefined }, { ...managedProfile, model: [] }, { ...managedProfile, model: [" "] }, { ...managedProfile, systemPrompt: "no boundary" },
      ...["task", "advisor", "eval", "hub"].map((tool) => ({ ...managedProfile, tools: ["read", tool] })),
    ]
    for (const profile of unsafe) {
      const runtime = harness(foreground, [], undefined, { profiles: [profile] })
      expect((await runtime.call("task", { agent: "task" }))?.reason).toContain("lacks the managed foreground leaf contract")
    }
  })

  it("SHOULD reject disabled profiles, model overrides and unavailable discovery", async () => {
    const disabled = harness({ ...foreground, "task.disabledAgents": ["task"] })
    expect((await disabled.call("task", { agent: "task" }))?.block).toBe(true)
    const override = harness({ ...foreground, "task.agentModelOverrides": { task: "@default" } })
    expect((await override.call("task", { agent: "task" }))?.reason).toContain("settings-level model override")
    const missing = harness(foreground, [], undefined, { discoveryError: true })
    expect((await missing.call("task", { agent: "task" }))?.reason).toContain("Cannot establish the effective OMP user profiles")
    expect(await missing.call("read")).toBeUndefined()
  })

  it("SHOULD reject advisor and prewalk overrides without disabling the explicit final refute model role", async () => {
    for (const key of ["task.agentAdvisor", "task.agentPrewalk"]) {
      for (const value of ["on", "@advisor", "@smol"]) {
        const runtime = harness({ ...foreground, [key]: { task: value } })
        expect((await runtime.call("task", { agent: "task" }))?.reason).toContain(key)
      }
      for (const value of ["off", " FALSE ", ""]) {
        const runtime = harness({ ...foreground, [key]: { task: value } }, [], undefined, { profiles: [{ ...managedProfile, model: ["@advisor"] }] })
        expect(await runtime.call("task", { agent: "task" })).toBeUndefined()
      }
    }
  })

  it("SHOULD check every enabled profile for Eval while task checks only its explicit selection", async () => {
    const profiles: Profile[] = [managedProfile, { name: "reviewer", source: "bundled" }]
    const runtime = harness(foreground, [], undefined, { profiles })
    expect(await runtime.call("task", { agent: "task" })).toBeUndefined()
    expect((await runtime.call("eval"))?.reason).toContain("Profile reviewer")
    const disabled = harness({ ...foreground, "task.disabledAgents": ["reviewer"] }, [], undefined, { profiles })
    expect(await disabled.call("eval")).toBeUndefined()
  })
})

describe("WHEN native OMP builds a worker prompt", () => {
  const scope = "§ Role\n[DELEGATION BOUNDARY]\nOwn only src/widget.ts.\n\n§ Context\nReady packet; leave other paths unchanged.\n\n§ Plan\nKeep the agreed interface."
  const protocol = "Yield protocol:\n- Omit type; fields go inside data.\n```ts\n{ produced: string, evidence: string[] }\n```\n"
  const completion = `\n§ Completion\nWhile work remains, keep calling tools and verifying.\n${protocol}\nGiving up is a last resort. Keep going until the ticket is closed.`
  const frame = `${scope}\n§ Coop\n# Validation\nScoped proof of your own change is fine.\n# Peers\nMessage siblings and wake parked agents.${completion}`
  const ambient = ["<skills>general catalog</skills> full SOP", "PROJECT\nBefore yielding, MUST verify significant behavioral changes."]

  it("SHOULD retain packet and yield schema without importing controller context or private QA", () => {
    const runtime = harness(undefined, ["yield"])
    const input = [ambient[0], frame, ambient[1]]
    const result = runtime.start(input)!
    expect(result.systemPrompt[0]).toBe(scope)
    const prompt = result.systemPrompt.join("\n")
    expect(prompt).toContain(protocol.trim())
    for (const forbidden of ["general catalog", "full SOP", "Before yielding, MUST verify", "Scoped proof", "Message siblings", "While work remains", "ticket is closed"]) {
      expect(prompt).not.toContain(forbidden)
    }
    expect(input).toEqual([ambient[0], frame, ambient[1]])
    expect(runtime.aborts).toBe(0)
  })

  it("SHOULD preserve native worktree confinement and workpool yield keys", () => {
    const runtime = harness(undefined, ["yield"])
    const workingTree = "# Working Tree\nYou are working in an isolated working tree at `/tmp/owned`.\nYou NEVER modify files outside this tree or in the original repository."
    const poolProtocol = "Workpool yield protocol:\n- Complete each assigned item with { key: <1-based number>, data: <outcome> }."
    const pool = `${scope}\n§ Coop\n${workingTree}\n# Peers\nDo not keep this roster.\n§ Completion\n${poolProtocol}\nGiving up is a last resort.`
    const result = runtime.start([ambient[0], pool, ambient[1]])!
    expect(result.systemPrompt[1]).toBe(workingTree)
    expect(result.systemPrompt.join("\n")).toContain(poolProtocol)
    expect(result.systemPrompt.join("\n")).not.toContain("roster")
    expect(runtime.aborts).toBe(0)
  })

  it("SHOULD abort unknown, ambiguous or unmanaged frames instead of using inherited instructions", () => {
    for (const chunks of [ambient, [frame, frame], [frame.replace("[DELEGATION BOUNDARY]", "unmanaged")], [frame.replace("Yield protocol:", "Unknown protocol:")], [frame.replace("§ Coop", "§ Coop\nambiguous\n§ Coop")]]) {
      const runtime = harness(undefined, ["yield"])
      const result = runtime.start(chunks)!
      expect(runtime.aborts).toBe(1)
      expect(result.systemPrompt).toHaveLength(1)
      expect(result.systemPrompt[0]).toStartWith("Blocked:")
      expect(result.systemPrompt[0]).not.toContain("full SOP")
    }
  })

  it("SHOULD leave root prompts unchanged", () => {
    const runtime = harness(foreground)
    expect(runtime.start(ambient)).toBeUndefined()
    expect(runtime.aborts).toBe(0)
  })
})

describe("WHEN an OMP session is a leaf", () => {
  it("SHOULD retain its leaf restriction after tools change, without reading root settings", async () => {
    const runtime = harness(undefined, ["yield"])
    expect(await runtime.call("bash", { async: false })).toBeUndefined()
    runtime.tools([])
    for (const tool of ["task", "advisor", "hub"]) expect((await runtime.call(tool))?.block).toBe(true)
    expect((await runtime.call("bash", { async: true }))?.block).toBe(true)
    expect(await runtime.call("read", { path: "README.md" })).toBeUndefined()
  })

  it("SHOULD reject peer wakeups in roots with native whitespace normalization", async () => {
    const runtime = harness(foreground)
    for (const name of [undefined, "", " \t\n"]) {
      expect((await runtime.call("hub", { op: "send", name }))?.block).toBe(true)
    }
  })
})

describe("WHEN native OMP finalizes a worker result", () => {
  it.each(["completed", "failed", "aborted"])("SHOULD seal %s without altering the transcript and reject live or cold revival", async (status) => {
    const root = harness(foreground)
    const child = harness(undefined, ["yield"])
    const transcript = readFileSync(child.sessionFile!, "utf8")
    expect(await child.call("read")).toBeUndefined()
    child.provider()
    expect(child.aborts).toBe(0)
    root.lifecycle({ status, sessionFile: child.sessionFile })
    const marker = `${child.sessionFile}.k-leaf-terminal`
    expect(statSync(marker).mode & 0o777).toBe(0o600)
    expect(readFileSync(child.sessionFile!, "utf8")).toBe(transcript)
    for (const runtime of [child, harness(undefined, ["yield"], child.sessionFile)]) {
      expect((await runtime.call("read"))?.reason).toContain("already returned")
      expect(runtime.start([])?.systemPrompt[0]).toContain("already returned")
      runtime.provider()
      expect(runtime.aborts).toBe(2)
    }
    root.lifecycle({ status: "started", sessionFile: child.sessionFile })
    root.lifecycle({ status: "completed", sessionFile: child.sessionFile })
    expect(readFileSync(marker, "utf8")).toBe("terminal\n")
    expect(await root.call("task", { agent: "task" })).toBeUndefined()
    root.provider()
    expect(root.aborts).toBe(0)
  })

  it("SHOULD leave started and provisional yields open, and never let a leaf seal siblings", async () => {
    const root = harness(foreground)
    const child = harness(undefined, ["yield"])
    for (const status of ["started", "success", "yield", undefined]) root.lifecycle({ status, sessionFile: child.sessionFile })
    child.result("yield")
    child.lifecycle({ status: "completed", sessionFile: child.sessionFile })
    child.provider()
    expect(await child.call("read")).toBeUndefined()
    expect(child.aborts).toBe(0)
    expect(existsSync(`${child.sessionFile}.k-leaf-terminal`)).toBe(false)
  })

  it("SHOULD report failed persistence and block new dispatch, while still sealing other completed workers", async () => {
    const root = harness(foreground)
    root.lifecycle({ status: "completed", sessionFile: join(fixtureDir, "missing", "worker.jsonl") })
    expect(root.result("task")?.isError).toBe(true)
    expect(root.result("eval")?.isError).toBe(true)
    for (const tool of ["task", "eval"]) expect((await root.call(tool))?.reason).toContain("Cannot persist")
    expect(await root.call("read")).toBeUndefined()
    expect(root.result("read")).toBeUndefined()
    const other = harness(undefined, ["yield"])
    root.lifecycle({ status: "completed", sessionFile: other.sessionFile })
    expect((await other.call("read"))?.reason).toContain("already returned")
  })

  it("SHOULD reject an in-flight admission if another worker cannot be sealed while settings reload", async () => {
    let finishReload!: () => void
    const reload = new Promise<void>((resolve) => { finishReload = resolve })
    const root = harness(foreground, [], undefined, { reload: () => reload })
    const pending = root.call("task", { agent: "task" })
    root.lifecycle({ status: "completed", sessionFile: join(fixtureDir, "missing", "during-admission.jsonl") })
    finishReload()
    expect((await pending)?.reason).toContain("Cannot persist")
  })

  it("SHOULD reject invalid completion paths and leaves without persistent session identity", async () => {
    for (const sessionFile of [undefined, "relative.jsonl", fixtureDir]) {
      const root = harness(foreground)
      root.lifecycle({ status: "completed", sessionFile })
      expect(root.result("task")?.isError).toBe(true)
    }
    const child = harness(undefined, ["yield"], null)
    expect((await child.call("read"))?.reason).toContain("persisted native session")
    child.provider()
    expect(child.aborts).toBe(1)
  })
})
