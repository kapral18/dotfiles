import type { EngineInterface, PromptOrigin, Register } from 'claude-code'

// The shared core: `,task hook <event>` reads JSON and answers JSON, the same for every harness (~/AGENTS.md §3 step 0).
type Answer = { context?: string; deny?: string; note?: string; instructions?: string; block?: string }

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
    if (e.command !== undefined || e.isMeta === true || !isTyped(e.origin)) return next(e)
    const { context } = await task($, 'prompt', { text: e.text })
    return next(context ? { ...e, context: [...(e.context ?? []), context] } : e)
  }).catch(($, e, next) => next(e))

  // Edits are checked before they run: the first one without a card is refused once, and one outside `Scope:` gets a note.
  on('tool.call', { tool: ['Edit', 'Write', 'NotebookEdit'] }, async ($, e, next) => {
    if (e.agentId !== undefined) return next(e)
    const path = 'notebook_path' in e ? e.notebook_path : e.file_path
    const input = { tool: e.tool, paths: [path], write: true, call_id: e.tool_use_id }
    const { deny } = await task($, 'tool', { ...input, phase: 'before' })
    if (deny) return { deny }
    const ran = await next(e)
    if (ran.deny !== undefined || ran.isError === true) return ran
    const { note } = await task($, 'tool', { ...input, phase: 'after' })
    return note ? { ...ran, context: [...(ran.context ?? []), note] } : ran
  }).catch(($, e, next) => next(e))

  // Every other main-loop call counts toward the zoom-out.
  on('tool.call', async ($, e, next) => {
    if (e.agentId !== undefined || e.tool === 'Edit' || e.tool === 'Write' || e.tool === 'NotebookEdit') return next(e)
    if (e.tool === 'Bash') await task($, 'tool', { tool: e.tool, phase: 'before', call_id: e.tool_use_id })
    const ran = await next(e)
    if (ran.deny !== undefined) return ran
    const backgroundId = e.tool === 'Bash' && ran.result && typeof ran.result === 'object' && 'backgroundTaskId' in ran.result ? ran.result.backgroundTaskId : undefined
    const untilStop = e.tool === 'Bash' && ran.result && typeof ran.result === 'object' && 'backgroundEndsWithFinalResponse' in ran.result && ran.result.backgroundEndsWithFinalResponse === true
    const { note } = await task($, 'tool', { tool: e.tool, phase: 'after', call_id: e.tool_use_id, background: Boolean(backgroundId), background_id: backgroundId, until_stop: Boolean(untilStop) })
    // GetTask can consume the completion notification, so its terminal result also settles the snapshot.
    const completed = e.tool === 'GetTask' && ran.result && typeof ran.result === 'object' && 'status' in ran.result && ran.result.status !== 'working'
      ? await task($, 'tool', { tool: 'Bash', phase: 'complete', call_id: e.tool_use_id, background_id: e.taskId })
      : {}
    const notes = [note, completed.note].filter((text): text is string => Boolean(text))
    return notes.length ? { ...ran, context: [...(ran.context ?? []), ...notes] } : ran
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
