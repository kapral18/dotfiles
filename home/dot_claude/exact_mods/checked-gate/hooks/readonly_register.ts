import type { EngineInterface, Register } from 'claude-code'

// Edits here are not part of the user's change.
const IGNORED = /^(\/private)?\/(tmp|var\/folders)\/|\/\.claude\/(plans|projects)\//
// A `Checked:` list header: `Checked:`, `**Checked:**`, or `## Checked:`.
const CHECKED = /^[\s>*_#-]*Checked(\*\*)?:/m
// The working tree's state: changed paths, a hash of the tracked diff, and a hash of untracked contents.
const SNAPSHOT =
  'git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 3\n' +
  'git --no-optional-locks status --porcelain=v1\n' +
  'git diff HEAD --no-ext-diff --binary 2>/dev/null | git hash-object --stdin\n' +
  'git ls-files --others --exclude-standard | git hash-object --stdin-paths | git hash-object --stdin'

const MESSAGE =
  'Files changed this turn, but the final message has no `Checked:` list. ' +
  'Per ~/AGENTS.md §3, add it: each claim with its evidence (a command and its result, or a file:line). ' +
  'If the change is not done, say so and list what is open.'

const snapshot = async ($: EngineInterface) => {
  const run = await $.process.run(['sh', '-c', SNAPSHOT], { timeoutMs: 20000 })
  return run.exitCode === 0 ? run.stdout : undefined
}

export const register: Register = on => {
  let isEdited = false
  // undefined: no Bash call yet this turn; null: the snapshot failed.
  let baseline: string | null | undefined

  on('turn.start', ($, e, next) => {
    isEdited = false
    baseline = undefined
    return next(e)
  })

  on('tool.call', { tool: ['Edit', 'Write', 'NotebookEdit'] }, async ($, e, next) => {
    const ran = await next(e)
    const path = 'notebook_path' in e ? e.notebook_path : e.file_path
    if (ran.deny === undefined && ran.isError !== true && !IGNORED.test(path)) isEdited = true
    return ran
  }).catch(($, e, next) => next(e))

  on('tool.call', { tool: 'Bash' }, async ($, e, next) => {
    if (!isEdited && baseline === undefined) baseline = (await snapshot($).catch(() => undefined)) ?? null
    return next(e)
  }).catch(($, e, next) => next(e))

  on('classic.Stop', async ($, e, next) => {
    if (e.stop_hook_active || CHECKED.test(e.last_assistant_message ?? '')) return next(e)
    let isChanged = isEdited
    if (!isChanged && typeof baseline === 'string') {
      const now = await snapshot($)
      isChanged = now !== undefined && now !== baseline
    }
    const below = await next(e)
    if (!isChanged) return below
    return { ...below, block: below.block ? `${below.block}\n\n${MESSAGE}` : MESSAGE }
  }).catch(($, e, next) => next(e))
}
