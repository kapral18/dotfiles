// Managed by chezmoi. Makes the main session act on advisor notes that land after its final answer.
import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent"

// OMP steers a final advisor note into a new turn only for a `concern` or `blocker`, and only while no user
// interrupt is in effect. A prompt or a queued message clears its interrupt flag, but the empty Enter that
// interrupts a run to send a queued message sets it again, as does cancelling an `ask`; the resumed run keeps it,
// and the note becomes a passive card. A `nit` is always a card. Either way the agent stopped until the user replied.
const FOLLOW_UP =
  "The advisor notes above arrived after your final answer. Weigh each against the evidence: fix what holds, " +
  "reject the rest with a one-line reason, then write the whole final answer again with the fixes folded in (~/AGENTS.md §8)."

type Message = { role?: string; customType?: string; stopReason?: string }

export default function (pi: ExtensionAPI) {
  // An advisor note the agent has not answered yet.
  let pending = false
  // The note outlived a settle OMP continued with its own prompt, so that turn's reply does not answer it.
  let carried = false
  // The last assistant message was a finished answer, not an interrupt or a tool call.
  let answered = false

  const drop = () => {
    pending = false
    carried = false
  }

  const followUp = () => {
    drop()
    pi.sendMessage({ customType: "advisor-followup", content: FOLLOW_UP, display: false }, { deliverAs: "steer", triggerTurn: true })
  }

  // OMP rebinds extensions to every subagent and advisor (`ctx.agent.kind === "sub"`); only the main session follows up.
  pi.on("message_end", (event, ctx) => {
    if (ctx.agent.kind === "sub") return
    const message = event.message as Message
    // A turn the user started (a prompt, a `/skill:` or collab prompt, by OMP's own rule) supersedes a pending note.
    // Other user-attributed messages, such as a `/tan` breadcrumb, can ride along with OMP's own continuations.
    if (pi.pi.isUserAuthoredMessage(event.message)) {
      drop()
      return
    }
    if (message.role === "assistant") {
      if (!carried) pending = false
      answered = message.stopReason === "stop"
      return
    }
    if (message.role !== "custom" || message.customType !== "advisor" || !answered) return
    // A note that lands once the session is idle has no settle left to wait for.
    if (ctx.isIdle() && !ctx.hasPendingMessages()) followUp()
    else pending = true
  })

  // A note delivered at the final turn boundary is answered by the steered turn OMP starts; one left as a card is not.
  // A settle OMP continues itself (a session_stop or todo continuation, a retry, background work) keeps the note
  // for the terminal settle, which always resolves it: a follow-up after a finished answer, else the note is dropped.
  pi.on("agent_end", (event, ctx) => {
    if (ctx.agent.kind === "sub" || !pending) return
    if (event.willContinue) carried = true
    else if (answered) followUp()
    else drop()
  })
}
