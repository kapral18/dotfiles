// Managed by chezmoi (source: home/dot_pi/agent/exact_extensions/read-supersede.ts).
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent"

// Port of OMP's read supersede (pi-agent-core compaction/pruning.ts): when the same file has
// been read more than once, older `read` results are replaced with a short notice before each
// provider call, so only the newest copy of a file rides in context. The read gate already
// refuses byte-identical re-reads, so this fires for legitimate re-reads of changed files.
//
// Cache guard, also from OMP: rewriting an earlier message invalidates the prompt cache from
// that point, so an older read is only superseded while the suffix after it is small
// (cheap to recache) or the session has idled long enough for the cache to be cold anyway.
// The rewrite is applied to the outgoing message list only; the session file keeps the
// original result, so nothing is lost on disk.

const SUPERSEDED_NOTICE = "[Superseded by a newer read of this file]"
// ~8k tokens, OMP's suffixTokenLimit, measured here in characters.
const SUFFIX_CHAR_LIMIT = 32_000
const IDLE_FLUSH_MS = 90 * 60_000

type Block = { type?: string; text?: string; id?: string; name?: string; arguments?: Record<string, unknown> }
type Msg = { role?: string; toolCallId?: string; toolName?: string; content?: Block[] | string }

function textLength(message: Msg): number {
  const content = message.content
  if (typeof content === "string") return content.length
  if (!Array.isArray(content)) return 0
  return content.reduce((n, b) => n + (typeof b?.text === "string" ? b.text.length : 0), 0)
}

export function supersedeReads(messages: Msg[], now: number, lastCall: number | null): Msg[] | undefined {
  const pathByCallId = new Map<string, string>()
  for (const message of messages) {
    if (message.role !== "assistant" || !Array.isArray(message.content)) continue
    for (const block of message.content) {
      if (block?.type === "toolCall" && block.name === "read" && typeof block.id === "string") {
        const path = block.arguments?.path
        if (typeof path === "string" && !path.includes("://")) pathByCallId.set(block.id, path)
      }
    }
  }
  const latestIndexByPath = new Map<string, number>()
  messages.forEach((message, index) => {
    if (message.role === "toolResult" && message.toolName === "read" && typeof message.toolCallId === "string") {
      const path = pathByCallId.get(message.toolCallId)
      if (path) latestIndexByPath.set(path, index)
    }
  })
  const idle = lastCall !== null && now - lastCall >= IDLE_FLUSH_MS
  let changed = false
  const out = messages.slice()
  for (let index = 0; index < messages.length; index++) {
    const message = messages[index]
    if (message.role !== "toolResult" || message.toolName !== "read" || typeof message.toolCallId !== "string") continue
    const path = pathByCallId.get(message.toolCallId)
    if (!path || latestIndexByPath.get(path) === index) continue
    const alreadyNotice =
      Array.isArray(message.content) && message.content.length === 1 && message.content[0]?.text === SUPERSEDED_NOTICE
    if (alreadyNotice) continue
    if (!idle) {
      let suffix = 0
      for (let j = index + 1; j < messages.length; j++) suffix += textLength(messages[j])
      if (suffix > SUFFIX_CHAR_LIMIT) continue
    }
    out[index] = { ...message, content: [{ type: "text", text: SUPERSEDED_NOTICE }] }
    changed = true
  }
  return changed ? out : undefined
}

export default function (pi: ExtensionAPI) {
  let lastCall: number | null = null
  pi.on("context", (event) => {
    const now = Date.now()
    try {
      const messages = supersedeReads(event.messages as Msg[], now, lastCall)
      return messages ? { messages: messages as typeof event.messages } : undefined
    } catch {
      return undefined
    } finally {
      lastCall = now
    }
  })
}
