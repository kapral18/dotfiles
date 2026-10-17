import { describe, expect, it } from "bun:test"
import followup from "../../home/dot_omp/private_agent/extensions/advisor-followup.ts"

type Handler = (event: unknown, ctx: unknown) => unknown

// A fake OMP host: records every message the extension sends and lets a test fire events.
function load() {
  const handlers = new Map<string, Handler>()
  const sent: { message: { customType: string }; options: unknown }[] = []
  const host = {
    on: (event: string, handler: Handler) => { handlers.set(event, handler) },
    sendMessage: (message: { customType: string }, options: unknown) => { sent.push({ message, options }) },
    // Stands in for OMP's `isUserAuthoredMessage`: a user message, or a user-attributed `/skill:` or collab prompt.
    pi: {
      isUserAuthoredMessage: (message: { role?: string; customType?: string; attribution?: string }) =>
        message.role === "user" || (message.attribution === "user" && ["skill-prompt", "collab-prompt"].includes(message.customType ?? "")),
    },
  }
  // The extension uses only `on`, `sendMessage`, and `pi.isUserAuthoredMessage` of OMP's much larger ExtensionAPI.
  followup(host as unknown as Parameters<typeof followup>[0])
  const state = { idle: false, kind: "main" }
  const ctx = () => ({ agent: { kind: state.kind }, isIdle: () => state.idle, hasPendingMessages: () => false })
  const answer = (stopReason = "stop") => handlers.get("message_end")!({ message: { role: "assistant", stopReason } }, ctx())
  const note = () => handlers.get("message_end")!({ message: { role: "custom", customType: "advisor" } }, ctx())
  const end = (willContinue?: boolean) => handlers.get("agent_end")!({ messages: [], willContinue }, ctx())
  const send = (message: object) => handlers.get("message_end")!({ message }, ctx())
  const prompt = () => send({ role: "user" })
  const skill = () => send({ role: "custom", customType: "skill-prompt", attribution: "user" })
  return { sent, state, answer, note, end, prompt, skill, send }
}

describe("advisor follow-up", () => {
  it("starts one turn for a note left as a card after the final answer", () => {
    const host = load()
    host.answer()
    host.note()
    host.end()
    host.end()
    expect(host.sent).toEqual([
      { message: expect.objectContaining({ customType: "advisor-followup" }), options: { deliverAs: "steer", triggerTurn: true } },
    ])
  })

  it("leaves a note alone once the agent answered it", () => {
    const host = load()
    host.answer()
    host.note()
    host.answer()
    host.end()
    expect(host.sent).toEqual([])
  })

  it("keeps a note through a turn OMP continues with its own prompt, then follows up", () => {
    const host = load()
    host.answer()
    host.note()
    host.end(true)
    expect(host.sent).toEqual([])
    // The continuation's own inputs, including a user-attributed `/tan` breadcrumb that rides along with it.
    host.send({ role: "custom", customType: "session-stop-continuation", attribution: "agent" })
    host.send({ role: "developer", attribution: "agent" })
    host.send({ role: "custom", customType: "background-tan-dispatch", attribution: "user" })
    host.answer()
    host.end()
    expect(host.sent).toHaveLength(1)
  })

  it("drops a carried note once the user sends a prompt or a skill command", () => {
    for (const input of ["prompt", "skill"] as const) {
      const host = load()
      host.answer()
      host.note()
      host.end(true)
      host[input]()
      host.answer()
      host.end()
      expect(host.sent).toEqual([])
    }
  })

  it("drops a carried note whose continuation was interrupted, so a later run gets no stale follow-up", () => {
    const host = load()
    host.answer()
    host.note()
    host.end(true)
    host.answer("aborted")
    host.end()
    host.answer()
    host.end()
    expect(host.sent).toEqual([])
  })

  it("follows up at once on a note that lands while the session is idle", () => {
    const host = load()
    host.answer()
    host.state.idle = true
    host.note()
    expect(host.sent).toHaveLength(1)
  })

  it("does not resume a run the user interrupted", () => {
    const host = load()
    host.answer("aborted")
    host.note()
    host.end()
    host.state.idle = true
    host.note()
    expect(host.sent).toEqual([])
  })

  it("ignores subagent and advisor sessions", () => {
    const host = load()
    host.state.kind = "sub"
    host.answer()
    host.note()
    host.end()
    expect(host.sent).toEqual([])
  })
})
