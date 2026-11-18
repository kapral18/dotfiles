import type { EngineInterface, PromptOrigin, Register } from 'claude-code'

// The shared core: `,task hook <event>` reads JSON and answers JSON, the same for every harness (~/AGENTS.md §3 step 0).
type Answer = { context?: string; note?: string; instructions?: string; block?: string }

// A failed or missing `,task` answers nothing, so the session goes on unguarded rather than stuck.
const task = async ($: EngineInterface, event: string, input: Record<string, unknown>): Promise<Answer> => {
  const cwd = await $.session.cwd()
  const session = await $.session.id()
  const run = await $.process
    .run([',task', 'hook', event, '--harness', 'claude', '--input', JSON.stringify({ ...input, cwd, session })], { timeoutMs: 15000 })
    .catch(() => undefined)
  if (run === undefined || run.exitCode !== 0) return {}
  try {
    const answer: unknown = JSON.parse(run.stdout)
    return typeof answer === 'object' && answer !== null ? (answer as Answer) : {}
  } catch {
    return {}
  }
}

// Prompt origins no person typed (PromptOrigin): a notice, a peer, a timer, or a plugin speaking for itself.
const UNTYPED = new Set(['task-notification', 'scheduled-trigger', 'peer', 'peer-send-message', 'coordinator', 'observer', 'observer-activity', 'auto-continuation'])
// No origin is the user's own (PromptSubmitResult).
const isTyped = (origin: PromptOrigin | undefined) =>
  origin === undefined || (origin.kind === 'plugin' ? origin.asUser === true : !UNTYPED.has(origin.kind))

// Native task-notification header order; only terminal notices complete a shell snapshot.
const COMPLETED_TASK = /^<task-notification>\s*<task-id>([^<]+)<\/task-id>\s*(?:<tool-use-id>([^<]+)<\/tool-use-id>\s*)?(?:<task-type>[^<]*<\/task-type>\s*)?(?:<output-file>[^<]*<\/output-file>\s*)?<status>(?:completed|failed|killed|stopped)<\/status>/

export const register: Register = on => {
  on('prompt.submit', async ($, e, next) => {
    if (e.origin?.kind === 'task-notification') {
      const completed = COMPLETED_TASK.exec(e.text)
      if (!completed) return next(e)
      const { note } = await task($, 'tool', { tool: 'Bash', phase: 'complete', call_id: completed[2], background_id: completed[1] })
      return next(note ? { ...e, context: [...(e.context ?? []), note] } : e)
    }
    // Only what a person typed: a task notice or a peer's message is no correction and must not reset the stop check.
    // What passes is the user's own words, and is marked so for the evidence ledger.
    if (e.command !== undefined || e.isMeta === true || !isTyped(e.origin)) return next(e)
    const { context } = await task($, 'prompt', { text: e.text, origin: 'human' })
    return next(context ? { ...e, context: [...(e.context ?? []), context] } : e)
  }).catch(($, e, next) => next(e))

  on('session.compact', async ($, e, next) => {
    if (e.agentId !== undefined || e.trigger === 'precompute') return next(e)
    const { instructions } = await task($, 'compact', {})
    return next(instructions ? { ...e, instructions: [e.instructions, instructions].filter(Boolean).join('\n\n') } : e)
  }).catch(($, e, next) => next(e))

  // Another Stop hook's send-back goes first; this one checks the answer that ends the turn.
  on('classic.Stop', async ($, e, next) => {
    const below = await next(e)
    if (below.block) return below
    // A subagent or workflow still in flight wakes the session when it ends; the turn is checked then.
    if ((e.background_tasks ?? []).some(job => job.type === 'subagent' || job.type === 'workflow')) return below
    const { block } = await task($, 'stop', { answer: e.last_assistant_message ?? '' })
    return block ? { ...below, block } : below
  }).catch(($, e, next) => next(e))
}
