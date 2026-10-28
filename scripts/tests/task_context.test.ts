import { afterAll, describe, expect, it } from "bun:test"
import { mkdtempSync, realpathSync, rmSync } from "node:fs"
import { homedir, tmpdir } from "node:os"
import { join } from "node:path"
import type { SessionBoundaryDraft } from "@earendil-works/pi-coding-agent"
import { checkpointWithReference, contextDrafts, projectCheckpoint, readContext, savedCheckpoint, TASK_CONTEXT } from "../../home/exact_lib/exact_shared/task_context.ts"

const piRoot = realpathSync(join(homedir(), ".local/share/pnpm-global-links/node_modules/@earendil-works/pi-coding-agent"))
const { SessionManager } = await import(join(piRoot, "dist/index.js"))
const temp = mkdtempSync(join(tmpdir(), "task-context-tests-"))
afterAll(() => rmSync(temp, { recursive: true, force: true }))
type Manager = InstanceType<typeof SessionManager>

function assistant(content: unknown[]) {
  return {
    role: "assistant", content, api: "openai-responses", provider: "fixture", model: "fixture",
    usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
    stopReason: "stop", timestamp: 1,
  }
}

function result(manager: Manager, text: string, options: { name?: string; args?: Record<string, unknown>; error?: boolean; image?: boolean } = {}) {
  const id = `call-${manager.getEntries().length}`
  const name = options.name ?? "read"
  manager.appendMessage(assistant([{ type: "toolCall", id, name, arguments: options.args ?? { path: "file.ts" } }]))
  return manager.appendMessage({
    role: "toolResult", toolCallId: id, toolName: name, isError: options.error ?? false, timestamp: 2,
    content: [{ type: "text", text }, ...(options.image ? [{ type: "image", data: "aW1hZ2U=", mimeType: "image/png" }] : [])],
  })
}

// Pi's boundary commit calls these same public append methods (agent-session.ts::_commitBoundaryDrafts).
function commit(manager: Manager, drafts: SessionBoundaryDraft[]) {
  for (const draft of drafts) {
    if (draft.type === "context_edit") manager.appendContextEdit(draft.targetId, draft.replacement)
    else if (draft.type === "custom_message") manager.appendCustomMessageEntry(draft.customType, draft.content, draft.display, draft.details)
    else if (draft.type === "custom") manager.appendCustomEntry(draft.customType, draft.data)
    else throw new Error("Unexpected compaction draft")
  }
}

function projectedText(manager: Manager, id: string) {
  return manager.buildSessionProjection().entries.find((entry: { sourceEntry: { id: string } }) => entry.sourceEntry.id === id)?.messages[0]?.content
}

describe("WHEN completed boundaries archive old text", () => {
  it("SHOULD shrink projection while preserving raw Unicode text, metadata and recent work across reopen", () => {
    const manager = SessionManager.create("/fixture", temp)
    manager.appendMessage({ role: "user", content: "Preserve my requirement", timestamp: 0 })
    const old = result(manager, "🙂é".repeat(25_000), { name: "bash" })
    const recent = result(manager, "recent ".repeat(6_000), { name: "bash" })
    manager.appendMessage(assistant([{ type: "text", text: "Next: fix the parser" }]))
    const drafts = contextDrafts(manager.buildSessionProjection().entries, "Goal: fix the parser", undefined)

    commit(manager, drafts)
    const reopened = SessionManager.open(manager.getSessionFile())

    expect(JSON.stringify(projectedText(reopened, old)).length).toBeLessThan(1000)
    expect(reopened.getEntry(old).message.content[0].text).toBe("🙂é".repeat(25_000))
    expect(reopened.getEntry(old).message.toolCallId).toBe("call-1")
    expect(projectedText(reopened, recent)[0].text).toBe("recent ".repeat(6_000))
    expect(reopened.buildSessionProjection().messages[0].content).toBe("Preserve my requirement")
    expect(reopened.getSessionId()).toBe(manager.getSessionId())
    expect(savedCheckpoint(reopened.getBranch())).toBe("Goal: fix the parser")
  })

  it.each([
    { error: true, image: false },
    { error: false, image: true },
  ])("SHOULD retain error or image content: %j", (options) => {
    const manager = SessionManager.inMemory("/fixture")
    const protectedId = result(manager, "protected".repeat(5000), options)
    result(manager, "recent".repeat(6000))

    const actual = contextDrafts(manager.buildSessionProjection().entries, "Goal", undefined)

    expect(actual.filter(draft => draft.type === "context_edit")).toEqual([])
    expect(manager.getEntry(protectedId).message.content[0].text).toBe("protected".repeat(5000))
  })

  it("SHOULD leave a small batch intact to avoid rewriting the provider prefix", () => {
    const manager = SessionManager.inMemory("/fixture")
    result(manager, "small".repeat(1000))
    result(manager, "recent".repeat(6000))

    const actual = contextDrafts(manager.buildSessionProjection().entries, "Goal", undefined)

    expect(actual.filter(draft => draft.type === "context_edit")).toEqual([])
  })

  it("SHOULD distinguish identical, changed and disjoint read results", () => {
    const manager = SessionManager.inMemory("/fixture")
    const stale = result(manager, "old line", { args: { path: "résumé.ts", offset: 200, limit: 1 } })
    const identical = result(manager, "same".repeat(10_000), { args: { path: "résumé.ts", offset: 1, limit: 30 } })
    const changed = result(manager, "earlier state".repeat(4000), { args: { path: "résumé.ts", offset: 50, limit: 30 } })
    const disjoint = result(manager, "other lines".repeat(4000), { args: { path: "résumé.ts", offset: 90, limit: 30 } })
    result(manager, "new state".repeat(5000), { args: { path: "résumé.ts", offset: 50, limit: 30 } })
    result(manager, "new line", { args: { path: "résumé.ts", offset: 200, limit: 1 } })
    result(manager, "same".repeat(10_000), { args: { limit: 30, path: "résumé.ts", offset: 1 } })

    commit(manager, contextDrafts(manager.buildSessionProjection().entries, "Goal", undefined))

    expect(projectedText(manager, identical)[0].text).toContain("identical later read")
    expect(projectedText(manager, stale)[0].text).toContain("changed in a later read")
    expect(projectedText(manager, stale)[0].text).not.toContain("old line")
    expect(projectedText(manager, changed)[0].text).not.toContain("identical later read")
    expect(projectedText(manager, disjoint)[0].text).not.toContain("identical later read")
    expect(readContext(manager.getBranch(), disjoint).text).toBe("other lines".repeat(4000).slice(0, 12_000))
  })

  it("SHOULD preserve disjoint small reads of the same file", () => {
    const manager = SessionManager.inMemory("/fixture")
    const first = result(manager, "first range", { args: { path: "file.ts", offset: 1, limit: 5 } })
    result(manager, "second range", { args: { path: "file.ts", offset: 20, limit: 5 } })

    commit(manager, contextDrafts(manager.buildSessionProjection().entries, "Goal", undefined))

    expect(projectedText(manager, first)[0].text).toBe("first range")
  })
})

describe("WHEN recovering task context", () => {
  it("SHOULD restore the current checkpoint after native compaction", () => {
    const manager = SessionManager.inMemory("/fixture")
    manager.appendCustomEntry(TASK_CONTEXT, "Goal: stale")
    manager.appendMessage({ role: "user", content: "New requirement", timestamp: 1 })
    const assistantId = manager.appendMessage(assistant([{ type: "text", text: "Next: add the regression" }]))
    commit(manager, contextDrafts(manager.buildSessionProjection().entries, "Goal: current; D1 open", savedCheckpoint(manager.getBranch())))
    manager.appendCompaction("Native summary", null, 200)

    const actual = projectCheckpoint(manager.buildSessionProjection().messages, checkpointWithReference(savedCheckpoint(manager.getBranch())!, manager.getBranch()))

    expect(actual.filter(message => message.role === "custom" && message.customType === TASK_CONTEXT)).toHaveLength(1)
    expect(JSON.stringify(actual)).toContain("Goal: current; D1 open")
    expect(JSON.stringify(actual)).not.toContain("Goal: stale")
    expect(JSON.stringify(actual)).toContain(assistantId)
    expect(readContext(manager.getBranch(), assistantId).text).toBe("Next: add the regression")
  })

  // Pi skips its usage-based overflow check when a context_edit follows the assistant message.
  it("SHOULD store a changed checkpoint once, outside model context", () => {
    const manager = SessionManager.inMemory("/fixture")
    manager.appendCustomEntry(TASK_CONTEXT, "Goal: A")

    const changed = contextDrafts(manager.buildSessionProjection().entries, "Goal: B", savedCheckpoint(manager.getBranch()))
    commit(manager, changed)

    expect(changed).toEqual([{ type: "custom", customType: TASK_CONTEXT, data: "Goal: B" }])
    expect(contextDrafts(manager.buildSessionProjection().entries, "Goal: B", savedCheckpoint(manager.getBranch()))).toEqual([])
    expect(contextDrafts(manager.buildSessionProjection().entries, "", undefined)).toEqual([])
  })

  it("SHOULD persist card clearing and keep archiving without a card", () => {
    const manager = SessionManager.inMemory("/fixture")
    manager.appendCustomEntry(TASK_CONTEXT, "Old goal")
    const old = result(manager, "old".repeat(20_000))
    result(manager, "recent".repeat(6000))

    commit(manager, contextDrafts(manager.buildSessionProjection().entries, "", savedCheckpoint(manager.getBranch())))

    expect(savedCheckpoint(manager.getBranch())).toBe("")
    expect(projectedText(manager, old)[0].text).toContain("Archived tool output")
    expect(manager.getEntry(old).message.content[0].text).toBe("old".repeat(20_000))
  })

  it("SHOULD preserve original pages without splitting Unicode code points", () => {
    const manager = SessionManager.inMemory("/fixture")
    const id = result(manager, "🙂".repeat(12_001))

    const actual = readContext(manager.getBranch(), id, 12_000)

    expect(actual).toEqual({ entryId: id, offset: 12_000, nextOffset: null, total: 12_001, text: "🙂" })
    expect(readContext(manager.getBranch(), id).nextOffset).toBe(12_000)
  })

  it("SHOULD reject another branch's history and invalid offsets", () => {
    const manager = SessionManager.inMemory("/fixture")
    const root = manager.appendMessage({ role: "user", content: "Start", timestamp: 0 })
    const id = result(manager, "abandoned")
    manager.branch(root)
    const current = result(manager, "current")

    expect(() => readContext(manager.getBranch(), id)).toThrow("active branch")
    expect(() => readContext(manager.getBranch(), current, -1)).toThrow("nonnegative integer")
    expect(() => readContext(manager.getBranch(), current, 0.5)).toThrow("nonnegative integer")
    expect(() => readContext(manager.getBranch(), current, 8)).toThrow("beyond")
    expect(readContext(manager.getBranch(), current, 7).text).toBe("")
  })
})
