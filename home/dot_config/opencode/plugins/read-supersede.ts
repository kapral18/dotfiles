// Managed by chezmoi (source: home/dot_config/opencode/plugins/read-supersede.ts).
import type { Plugin } from "@opencode-ai/plugin"

// Port of OMP's read supersede for OpenCode, the same rule as the Pi extension
// (~/.pi/agent/extensions/read-supersede.ts): when one file was read more than once, the
// older `read` results are replaced with a short notice on the message list handed to the
// provider (experimental.chat.messages.transform runs right before toModelMessages in
// packages/opencode/src/session/prompt.ts, on a list reloaded from the store each step),
// so only the newest copy of a file rides in context. The store keeps the original output.
//
// Cache guard (OMP): rewriting an earlier message invalidates the prompt cache from there,
// so an older read is only superseded while the suffix after it is small (cheap to recache)
// or the session idled long enough for the cache to be cold anyway.
//
// OpenCode's own `compaction.prune` (default off, packages/core/src/v1/config/config.ts) is
// broader: it clears every old tool output beyond a 40k-token tail. It stays off here on
// purpose; only duplicate file copies are dropped, never a result the model has once.

const SUPERSEDED_NOTICE = "[Superseded by a newer read of this file]"
// ~8k tokens, OMP's suffixTokenLimit, measured in characters.
const SUFFIX_CHAR_LIMIT = 32_000
const IDLE_FLUSH_MS = 90 * 60_000

type ToolState = {
  status?: string
  input?: { filePath?: unknown; offset?: unknown; limit?: unknown }
  output?: string
  attachments?: unknown[]
  time?: { compacted?: number }
}
type Part = { type?: string; tool?: string; text?: string; state?: ToolState }
type WithParts = { info?: { role?: string }; parts: Part[] }

function partLength(part: Part): number {
  if (typeof part.text === "string") return part.text.length
  const output = part.state?.output
  return typeof output === "string" ? output.length : 0
}

function wholeReadPath(part: Part): string | undefined {
  if (part.type !== "tool" || part.tool !== "read") return undefined
  const state = part.state
  if (!state || state.status !== "completed" || state.time?.compacted) return undefined
  if (state.input?.offset || state.input?.limit) return undefined
  const path = state.input?.filePath
  return typeof path === "string" && path ? path : undefined
}

/** Mutates `messages` in place; returns how many older read results were superseded. */
export function supersedeReadParts(messages: WithParts[], now: number, lastCall: number | null): number {
  const flat: { part: Part; index: number }[] = []
  for (const message of messages) for (const part of message.parts ?? []) flat.push({ part, index: flat.length })
  const latestByPath = new Map<string, number>()
  for (const { part, index } of flat) {
    const path = wholeReadPath(part)
    if (path) latestByPath.set(path, index)
  }
  const idle = lastCall !== null && now - lastCall >= IDLE_FLUSH_MS
  let changed = 0
  for (const { part, index } of flat) {
    const path = wholeReadPath(part)
    if (!path || latestByPath.get(path) === index) continue
    if (part.state?.output === SUPERSEDED_NOTICE) continue
    if (!idle) {
      let suffix = 0
      for (let j = index + 1; j < flat.length; j++) suffix += partLength(flat[j].part)
      if (suffix > SUFFIX_CHAR_LIMIT) continue
    }
    part.state!.output = SUPERSEDED_NOTICE
    part.state!.attachments = []
    changed++
  }
  return changed
}

export const ReadSupersedePlugin: Plugin = async () => {
  let lastCall: number | null = null
  return {
    "experimental.chat.messages.transform": async (_input, output) => {
      const now = Date.now()
      try {
        supersedeReadParts(output.messages as unknown as WithParts[], now, lastCall)
      } catch {
        // a failed rewrite must never break the request
      } finally {
        lastCall = now
      }
    },
  }
}
