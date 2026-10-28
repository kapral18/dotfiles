import type { ProjectedSessionEntry, SessionBoundaryDraft, SessionEntry } from "@earendil-works/pi-coding-agent"
import { messageText } from "./intent_guard.ts"

export const TASK_CONTEXT = "task-context"
const ARCHIVED = "[Archived tool output; "
const RECENT_CHARS = 32_000
const MIN_BATCH_CHARS = 32_000
const MIN_OUTPUT_CHARS = 2_000
const PAGE_CHARS = 12_000

type Message = ProjectedSessionEntry["messages"][number]

function plainText(message: Message): string | undefined {
  if (!("content" in message) || !Array.isArray(message.content)) return undefined
  if (!message.content.every(block => block.type === "text")) return undefined
  return messageText(message)
}

export function savedCheckpoint(branch: readonly SessionEntry[]): string | undefined {
  for (let i = branch.length - 1; i >= 0; i--) {
    const entry = branch[i]
    if (entry.type === "custom" && entry.customType === TASK_CONTEXT && typeof entry.data === "string") return entry.data
  }
}

export function checkpointWithReference(checkpoint: string, branch: readonly SessionEntry[]): string {
  if (!checkpoint) return ""
  const last = branch.findLast(entry => entry.type === "message" && entry.message.role === "assistant" && messageText(entry.message))
  if (!last || last.type !== "message") return checkpoint
  return `${checkpoint}\nLatest assistant note (unverified; task_context_read entryId=${last.id}):\n${Array.from(messageText(last.message)).slice(0, 600).join("")}`
}

/** Keep a single current checkpoint, including after native compaction removed its projection. */
export function projectCheckpoint(messages: readonly Message[], checkpoint: string): Message[] {
  const out = messages.filter(message => message.role !== "custom" || message.customType !== TASK_CONTEXT)
  if (checkpoint) out.push({ role: "custom", customType: TASK_CONTEXT, content: checkpoint, display: false, timestamp: 0 })
  return out
}

function readCalls(entries: readonly ProjectedSessionEntry[]): Map<string, string> {
  const calls = new Map<string, string>()
  for (const { messages } of entries) for (const message of messages) {
    if (message.role !== "assistant") continue
    for (const block of message.content) {
      if (block.type !== "toolCall" || block.name !== "read") continue
      // The complete argument object must agree; ranges and unknown future options stay distinct.
      calls.set(block.id, JSON.stringify(Object.entries(block.arguments).sort(([a], [b]) => a.localeCompare(b))))
    }
  }
  return calls
}

/**
 * Drafts change only model projection. Original entries and call/result metadata remain in Pi's log.
 * The checkpoint is stored as a non-context entry: a context_edit after the assistant message turns off Pi's usage-based overflow check.
 */
export function contextDrafts(entries: readonly ProjectedSessionEntry[], checkpoint: string, saved: string | undefined): SessionBoundaryDraft[] {
  const drafts: SessionBoundaryDraft[] = checkpoint === (saved ?? "") ? [] : [{ type: "custom", customType: TASK_CONTEXT, data: checkpoint }]
  const calls = readCalls(entries)
  const reads = new Map<string, string>()
  const archives: SessionBoundaryDraft[] = []
  let suffix = 0
  let savedChars = 0
  for (let i = entries.length - 1; i >= 0; i--) {
    const { sourceEntry, messages } = entries[i]
    for (const message of messages) {
      const recent = suffix < RECENT_CHARS
      suffix += messageText(message).length
      if (message.role !== "toolResult" || message.isError) continue
      const text = plainText(message)
      if (text === undefined || text.startsWith(ARCHIVED)) continue
      const read = message.toolName === "read" ? calls.get(message.toolCallId) : undefined
      const later = read === undefined ? undefined : reads.get(read)
      if (read !== undefined) reads.set(read, text)
      if (recent || (later === undefined && text.length < MIN_OUTPUT_CHARS)) continue
      const reason = later === undefined ? "" : later === text ? "identical later read; " : "changed in a later read; "
      const label = `${ARCHIVED}${reason}task_context_read entryId=${sourceEntry.id}]`
      let notice = `${label}\n${Array.from(text).slice(0, 240).join("")}`
      if (notice.length >= text.length) {
        if (later === undefined || later === text) continue
        notice = label
      }
      archives.push({ type: "context_edit", targetId: sourceEntry.id, replacement: { content: notice } })
      savedChars += text.length - notice.length
    }
  }
  if (savedChars >= MIN_BATCH_CHARS) drafts.push(...archives)
  return drafts
}

/** Read only active-branch text, with Unicode code-point offsets and a bounded page. */
export function readContext(branch: readonly SessionEntry[], entryId: string, offset = 0) {
  if (!Number.isSafeInteger(offset) || offset < 0) throw new Error("offset must be a nonnegative integer")
  const entry = branch.find(entry => entry.id === entryId)
  if (!entry || entry.type !== "message") throw new Error("Text entry not found on the active branch")
  const text = Array.from(messageText(entry.message))
  if (offset > text.length) throw new Error("offset is beyond the entry")
  const end = Math.min(offset + PAGE_CHARS, text.length)
  return { entryId, offset, nextOffset: end < text.length ? end : null, total: text.length, text: text.slice(offset, end).join("") }
}
