import type { On } from 'claude-code'
import { expect, test } from 'claude-code/testing'

const ran = (stdout: string, exitCode = 0) => ({ exitCode, stdout, stderr: '', isStdoutTruncated: false, isStderrTruncated: false })
const edit = (file_path: string) => ({ tool: 'Edit', file_path, old_string: 'a', new_string: 'b' }) as const
const stop = (last_assistant_message: string, stop_hook_active = false) => ({ stop_hook_active, last_assistant_message })

// The engine beneath the plugin; `tree` is what each working-tree snapshot reads.
const engine = (on: On, tree: string[] = []) => {
  on('turn.start', ($, e) => ({ turnId: e.turnId }))
  on('process.run', () => ({ value: tree[0] === 'fail' ? ran('', 3) : ran(tree.shift() ?? 'same') }))
  on('tool.call', ($, e) => (e.tool === 'Edit' && e.file_path.endsWith('denied.ts') ? { deny: 'no' } : { result: {} as never }))
  on('classic.Stop', () => ({}))
}

test('sends a turn that edited files back once when Checked: is missing', async ($, on) => {
  engine(on)
  await $.turn.start({ text: 'fix it', turnId: 't1' })
  await $.tool.call(edit('/repo/a.ts'))
  expect((await $.classic.Stop(stop('Done.'))).block).toMatch(/no `Checked:` list/)
  expect((await $.classic.Stop(stop('Done.', true))).block).toBeUndefined()
  expect((await $.classic.Stop(stop('Done.\nChecked the logs, nothing else.'))).block).toMatch(/Checked:/)
  expect((await $.classic.Stop(stop('Done.\n\n**Checked:**\n- tests pass'))).block).toBeUndefined()
})

test('passes a turn without changes, or with only scratch, plan, or refused edits', async ($, on) => {
  engine(on)
  await $.turn.start({ text: 'explain', turnId: 't1' })
  expect((await $.classic.Stop(stop('Answer.'))).block).toBeUndefined()
  await $.tool.call(edit('/tmp/x/a.ts'))
  await $.tool.call(edit('/Users/u/.claude/plans/p.md'))
  await $.tool.call(edit('/repo/denied.ts'))
  expect((await $.classic.Stop(stop('Answer.'))).block).toBeUndefined()
})

test('catches a change made through Bash by comparing working-tree snapshots', async ($, on) => {
  engine(on, ['before', 'after', 'same', 'same'])
  await $.turn.start({ text: 'sed it', turnId: 't1' })
  await $.tool.call({ tool: 'Bash', command: "sed -i '' s/a/b/ a.ts" })
  expect((await $.classic.Stop(stop('Done.'))).block).toMatch(/Checked:/)
  await $.turn.start({ text: 'look', turnId: 't2' })
  await $.tool.call({ tool: 'Bash', command: 'git log -1' })
  expect((await $.classic.Stop(stop('Answer.'))).block).toBeUndefined()
})

test('a new turn forgets the edits of the last one', async ($, on) => {
  engine(on)
  await $.turn.start({ text: 'fix', turnId: 't1' })
  await $.tool.call(edit('/repo/a.ts'))
  await $.turn.start({ text: 'thanks', turnId: 't2' })
  expect((await $.classic.Stop(stop('Ok.'))).block).toBeUndefined()
})

test('passes a Bash change that the final message reports with Checked', async ($, on) => {
  engine(on, ['before', 'after'])
  await $.turn.start({ text: 'sed it', turnId: 't1' })
  await $.tool.call({ tool: 'Bash', command: "sed -i '' s/a/b/ a.ts" })
  expect((await $.classic.Stop(stop('Done.\n\nChecked:\n- a.ts:1 changed'))).block).toBeUndefined()
})

test('does not guess when the snapshot fails outside a git repo', async ($, on) => {
  engine(on, ['fail'])
  await $.turn.start({ text: 'touch it', turnId: 't1' })
  await $.tool.call({ tool: 'Bash', command: 'touch x' })
  expect((await $.classic.Stop(stop('Done.'))).block).toBeUndefined()
})

test('adds its message to a block from below', async ($, on) => {
  on('turn.start', ($, e) => ({ turnId: e.turnId }))
  on('process.run', () => ({ value: ran('same') }))
  on('tool.call', () => ({ result: {} as never }))
  on('classic.Stop', () => ({ block: 'other gate' }))
  await $.turn.start({ text: 'fix', turnId: 't1' })
  await $.tool.call(edit('/repo/a.ts'))
  expect((await $.classic.Stop(stop('Done.'))).block).toMatch(/^other gate\n\nFiles changed this turn/)
})
