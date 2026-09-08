// Managed by chezmoi (source: home/dot_omp/private_agent/extensions/runtime-parity.ts).
// OMP runtime defaults that mirror the shared Cursor contracts.

import { lstatSync, realpathSync, writeFileSync } from "node:fs"
import { isAbsolute, join } from "node:path"
import type { ExtensionAPI, ExtensionContext } from "@oh-my-pi/pi-coding-agent"

const SEARCH_TOOLS = ["grep", "find", "ls"]
const TOOL_SELECTION_FLAGS = ["--tools", "-t", "--exclude-tools", "-xt", "--no-tools", "-nt", "--no-builtin-tools", "-nbt"]
const TERMINAL_SUFFIX = ".k-leaf-terminal"

function terminalProblem(ctx: ExtensionContext): string | undefined {
  const sessionFile = ctx.sessionManager.getSessionFile()
  if (!sessionFile) return "Managed OMP leaves require a persisted native session for terminal enforcement."
  try {
    lstatSync(`${sessionFile}${TERMINAL_SUFFIX}`)
    return "This worker already returned its terminal result. Do not revive it or replace its artifact."
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return
    return "Cannot inspect the worker terminal marker. Do not continue or bypass the guard."
  }
}

function sealTerminal(data: unknown): string | undefined {
  if (!data || typeof data !== "object") return
  const event = data as { status?: string; sessionFile?: string }
  if (!["completed", "failed", "aborted"].includes(event.status ?? "")) return
  const { sessionFile } = event
  try {
    if (typeof sessionFile !== "string" || !isAbsolute(sessionFile) || !sessionFile.endsWith(".jsonl") || !lstatSync(sessionFile).isFile()) {
      return "Cannot seal a finalized OMP worker without its native session file. Further dispatch is blocked."
    }
    // Native finalizeRunResult emits this event after saving/classifying the
    // authoritative result, unlike provisional yields and agent_end pauses.
    // A separate exclusive marker leaves both transcript and result untouched.
    writeFileSync(`${sessionFile}${TERMINAL_SUFFIX}`, "terminal\n", { flag: "wx", mode: 0o600 })
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "EEXIST") return
    return "Cannot persist the finalized OMP worker boundary. Further dispatch is blocked; do not retry or bypass it."
  }
}

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

async function dispatchSettingsProblem(pi: ExtensionAPI): Promise<string | undefined> {
  // The shipped CLI gives its root the bundled Settings singleton (main.ts).
  // Read through pi.pi: importing the source/legacy settings module can create
  // a different singleton with defaults. Never mutate process-wide settings.
  try {
    const settings = pi.pi.Settings.instance
    // Native subagent preflight reloads these layers too. Admit the same
    // on-disk configuration, not a stale snapshot from session startup.
    await settings.reloadFromDisk()
    const unsafe = (["bash.autoBackground.enabled", "eval.autoBackground.enabled"] as const)
      .filter((key) => settings.get(key) !== false)
    if (unsafe.length === 0) return
    return `Worker dispatch requires foreground defaults. Disable ${unsafe.join(" and ")} in the effective OMP configuration before dispatch; do not retry unchanged or launch another harness.`
  } catch {
    return "Cannot establish OMP CLI foreground settings. Worker dispatch is blocked; do not bypass this guard through another harness or settings module."
  }
}

async function dispatchProfileProblem(pi: ExtensionAPI, ctx: ExtensionContext, toolName: string, input: Record<string, unknown>): Promise<string | undefined> {
  try {
    const { agents } = await pi.pi.discoverAgents(ctx.cwd)
    const settings = pi.pi.Settings.instance
    const disabled = settings.get("task.disabledAgents") ?? []
    const packets = Array.isArray(input.tasks) ? input.tasks : [input]
    const requested: unknown[] = toolName === "task"
      ? packets.map((packet: unknown) => packet && typeof packet === "object" && "agent" in packet ? packet.agent : undefined)
      : agents.filter((agent) => !disabled.includes(agent.name)).map((agent) => agent.name)
    const names = requested.filter((name): name is string => typeof name === "string" && /^[A-Za-z0-9_-]+$/.test(name))
    if (names.length === 0 || names.length !== requested.length) {
      return "Task dispatch requires explicit managed profile names in every packet. Do not rely on an implicit native default."
    }
    const profileDir = realpathSync(join(pi.pi.getAgentDir(), "agents"))
    for (const name of new Set(names)) {
      const agent = agents.find((candidate) => candidate.name === name)
      if (!agent || disabled.includes(name) || agent.source !== "user" || !agent.filePath || realpathSync(agent.filePath) !== join(profileDir, `${name}.md`)) {
        return `Profile ${name} is not the enabled managed user profile. Project, plugin and bundled replacements cannot dispatch workers.`
      }
      if (agent.blocking !== true || agent.spawns || agent.advisor || agent.prewalk || !agent.tools?.length || agent.tools.some((tool) => ["task", "advisor", "eval", "hub"].includes(tool)) || !agent.model?.length || agent.model.some((model) => !model.trim()) || !agent.systemPrompt.includes("[DELEGATION BOUNDARY]")) {
        return `Profile ${name} lacks the managed foreground leaf contract. Do not launch it or substitute another model.`
      }
      if (settings.get("task.agentModelOverrides")?.[name] !== undefined) {
        return `Profile ${name} has a settings-level model override. Use its registry-rendered model instead of bypassing the lane.`
      }
      for (const key of ["task.agentAdvisor", "task.agentPrewalk"] as const) {
        const value = settings.get(key)?.[name]
        if (value !== undefined && !["", "off", "false"].includes(value.trim().toLowerCase())) {
          return `Profile ${name} enables ${key}. Worker advisors and automatic model handoffs are not leaf packets; disable this override before dispatch.`
        }
      }
    }
  } catch {
    return "Cannot establish the effective OMP user profiles. Worker dispatch is blocked; do not bypass native discovery or invoke another harness."
  }
}

async function guardDispatch(pi: ExtensionAPI, ctx: ExtensionContext, toolName: string, input: Record<string, unknown>, terminalFailure: () => string | undefined) {
  const reason = await dispatchSettingsProblem(pi) ?? await dispatchProfileProblem(pi, ctx, toolName, input)
  // A different root-owned task can finalize while discovery is awaited.
  const failure = terminalFailure() ?? reason
  if (failure) return { block: true as const, reason: failure }
}

function leafSystemPrompt(chunks: string[]): string[] | undefined {
  // OMP inserts one separate native subagent frame between its general and
  // project prompts. Keep packet data verbatim; discard ambient root workflow.
  const frames = chunks.filter((chunk) => chunk.startsWith("§ Role\n") && chunk.includes("\n§ Coop\n"))
  if (frames.length !== 1) return
  const [scope, ...cooperation] = frames[0].split("\n§ Coop\n")
  if (!scope.includes("[DELEGATION BOUNDARY]") || cooperation.length !== 1) return
  const [coop, ...completion] = cooperation[0].split("\n§ Completion\n")
  if (completion.length !== 1) return
  const protocol = completion[0].match(/(?:^|\n)((?:Workpool yield|Yield) protocol:\n[\s\S]*?)\nGiving up is a last resort\./)?.[1]
  if (!protocol) return
  const workingTree = coop.match(/(?:^|\n)(# Working Tree\n[\s\S]*?)(?=\n# |$)/)?.[1]
  return [
    scope.trim(),
    ...(workingTree ? [workingTree.trim()] : []),
    `§ Completion\n${protocol.trim()}\n\nReturn the assigned packet's terminal artifact or concrete blocker. A research or production worker MUST NOT run private verification, review, audit, refutation, or convergence. A final Verify worker MUST NOT repeat completed checks or launch another lane. Do not continue after the terminal result.`,
  ]
}

export default function (pi: ExtensionAPI) {
  // Native runSubprocess installs yield in every child, independent of prompt
  // markers or profile names. Latch the capability so active-tool edits cannot
  // turn a leaf back into a root. Explicit-yield roots are restricted as well.
  let leaf = false
  let sealProblem: string | undefined
  const isLeaf = () => (leaf ||= pi.getAllTools().some((tool) => tool.name === "yield"))
  pi.events.on("task:subagent:lifecycle", (data) => {
    if (isLeaf()) return
    const problem = sealTerminal(data)
    sealProblem ??= problem
  })
  pi.on("tool_result", (event) => {
    if (!isLeaf() && sealProblem && ["task", "eval"].includes(event.toolName)) {
      return { content: [...event.content, { type: "text", text: sealProblem }], isError: true }
    }
  })
  // Peer messages wake parked/finished agents in native OMP. Managed workflows
  // use terminal returns instead; named process stdin remains available.
  pi.on("tool_call", (event, ctx) => {
    if (isLeaf()) {
      const reason = terminalProblem(ctx)
      if (reason) return { block: true, reason }
    }
    const input = event.input as { async?: boolean; op?: string; name?: string }
    if (leaf && (input.async === true || ["task", "advisor", "hub"].includes(event.toolName))) {
      return { block: true, reason: "Leaf workers cannot start background work or orchestrate agents/processes. Use foreground tools and return the packet result once; the root owns long-running work." }
    }
    // Project/CLI overlays outrank the managed config. Check immediately before
    // native dispatch snapshots root settings into worker tool constructors.
    // Eval can dispatch agents too. Leaf Eval is not a managed profile tool.
    if (!leaf && ["task", "eval"].includes(event.toolName)) {
      if (sealProblem) return { block: true, reason: sealProblem }
      return guardDispatch(pi, ctx, event.toolName, event.input, () => sealProblem)
    }
    if (event.toolName !== "hub") return
    if (input.op === "send" && !input.name?.trim()) {
      return { block: true, reason: "Peer messaging can reopen completed workers. Use the packet's terminal result; do not message or revive agents." }
    }
  })
  pi.on("session_start", () => {
    isLeaf()
    enableSearchTools(pi)
  })
  pi.on("before_provider_request", (_event, ctx) => {
    if (isLeaf() && terminalProblem(ctx)) ctx.abort()
  })
  pi.on("before_agent_start", (event, ctx) => {
    if (!isLeaf()) return
    const reason = terminalProblem(ctx)
    if (reason) {
      ctx.abort()
      return { systemPrompt: [reason] }
    }
    const systemPrompt = leafSystemPrompt(event.systemPrompt)
    if (systemPrompt) return { systemPrompt }
    // Unknown frames must not fall back to an inherited controller prompt.
    // Native abort invalidates promptGeneration before provider dispatch.
    ctx.abort()
    return { systemPrompt: ["Blocked: OMP leaf prompt shape or managed packet boundary is missing. Do not execute the assignment or discover another workflow."] }
  })
}
