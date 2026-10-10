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
  await $.turn.start({ text: 'again', turnId: 't2' })
  await $.tool.call(edit('/repo/a.ts'))
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
  const block = (await $.classic.Stop(stop('Done.'))).block
  expect(block).toMatch(/^other gate\n\nFiles changed this turn/)
  // One reminder to answer the user, last, after every message.
  expect(block?.match(/Your reply is the final message/g)).toHaveLength(1)
  expect(block).toMatch(/then address this feedback after it\.$/)
})

// The engine beneath the question checks: every tool call succeeds and the tree never changes.
const toolEngine = (on: On) => {
  on('turn.start', ($, e) => ({ turnId: e.turnId }))
  on('process.run', () => ({ value: ran('same') }))
  on('tool.call', () => ({ result: {} as never }))
  on('classic.Stop', () => ({}))
}
const bash = (command: string) => ({ tool: 'Bash', command, description: 'test' }) as const

test('counts a subagent edit as a change', async ($, on) => {
  toolEngine(on)
  await $.turn.start({ text: 'delegate', turnId: 't1' })
  await $.tool.call(bash('make check'))
  await $.tool.call({ ...edit('/repo/a.ts'), agentId: 'worker-1' } as never)
  expect((await $.classic.Stop(stop('Done.'))).block).toMatch(/no `Checked:` list/)
})

test('a continuation after a send-back keeps the turn and its once-only checks', async ($, on) => {
  toolEngine(on)
  await $.turn.start({ text: 'fix it', turnId: 't1' })
  await $.tool.call(bash('ls'))
  expect((await $.classic.Stop(stop('Apply?'))).block).toMatch(/ends with a question/)
  await $.turn.start({ text: '', turnId: 't1-continue' })
  await $.tool.call(bash('ls'))
  expect((await $.classic.Stop(stop('Apply?', true))).block).toBeUndefined()
  await $.turn.start({ text: 'fix it, and ask me before you push', turnId: 't2' })
  await $.tool.call(edit('/repo/a.ts'))
  expect((await $.classic.Stop(stop('Done.'))).block).toMatch(/no `Checked:` list/)
  await $.turn.start({ text: '', turnId: 't2-continue' })
  await $.tool.call(bash('ls'))
  expect((await $.classic.Stop(stop('Checked:\n- a.ts:1 holds it\n\nPush it?', true))).block).toBeUndefined()
})

test('sends a tool-using turn back once when the reply ends with a question', async ($, on) => {
  toolEngine(on)
  await $.turn.start({ text: 'look', turnId: 't1' })
  expect((await $.classic.Stop(stop('Which file do you mean?'))).block).toBeUndefined()
  await $.tool.call(bash('ls'))
  expect((await $.classic.Stop(stop('I found two options.\n\nShould I apply the fix?'))).block).toMatch(/ends with a question/)
  expect((await $.classic.Stop(stop('Should I apply the fix?', true))).block).toBeUndefined()
  await $.turn.start({ text: 'look again', turnId: 't2' })
  await $.tool.call(bash('ls'))
  expect((await $.classic.Stop(stop('Done.\n\n```sh\nread -p "go?"\n```'))).block).toBeUndefined()
  expect((await $.classic.Stop(stop('Is it **done?**'))).block).toMatch(/ends with a question/)
})

test('keeps a question the user asked for', async ($, on) => {
  toolEngine(on)
  await $.turn.start({ text: 'Fix it, then ask me whether to run it.', turnId: 't1' })
  await $.tool.call(bash('ls'))
  expect((await $.classic.Stop(stop('Fixed. Should I run it?'))).block).toBeUndefined()
  await $.turn.start({ text: 'Fix it. End your reply by asking me whether to run it.', turnId: 't2' })
  await $.tool.call(bash('ls'))
  expect((await $.classic.Stop(stop('Fixed. Should I run it?'))).block).toBeUndefined()
  for (const [n, text] of ["so you don't even need to ask me but just apply", 'Fix it without asking me.', 'Never ask us for approval.'].entries()) {
    await $.turn.start({ text, turnId: `n${n}` })
    await $.tool.call(bash('ls'))
    expect((await $.classic.Stop(stop('Should I apply it?'))).block, text).toMatch(/ends with a question/)
  }
  const invited = [
    "Don't hesitate to ask me.",
    'If it is not clear, ask me.',
    'If not sure ask me.',
    "Fix it. If anything isn't clear ask me.",
    'If you get stuck, stop and ask me.',
    'Please stop guessing and ask me.',
    'Avoid guessing but ask me when unsure.',
    'Stop guessing, just ask me.',
  ]
  const refused = [
    'You don’t need to ask me, just fix it.',
    "Don't keep asking me.",
    'I do not want you to ask me.',
    'No need for you to ask me.',
    'Stop asking me and just fix it.',
    'Quit asking me questions.',
    'Avoid asking me anything.',
    'Stop constantly asking me questions.',
    'Please avoid always asking me.',
    'No questions; dont ask me.',
  ]
  for (const [n, text] of [...invited, ...refused].entries()) {
    await $.turn.start({ text, turnId: `h${n}` })
    await $.tool.call(bash('ls'))
    const block = (await $.classic.Stop(stop('Should I apply it?'))).block
    if (invited.includes(text)) expect(block, text).toBeUndefined()
    else expect(block, text).toMatch(/ends with a question/)
  }
})

test('leaves a question marked as the user\'s decision', async ($, on) => {
  toolEngine(on)
  await $.turn.start({ text: 'draft the comment', turnId: 't1' })
  await $.tool.call(bash('ls'))
  expect((await $.classic.Stop(stop('Draft:\n\n> text\n\nDecision needed: post it to PR 12?'))).block).toBeUndefined()
  await $.turn.start({ text: 'fix it', turnId: 't2' })
  await $.tool.call(bash('ls'))
  expect((await $.classic.Stop(stop('Done.\n\nDecision needed: none.\n\nWant me to also push it?'))).block).toMatch(/ends with a question/)
  await $.turn.start({ text: 'fix it', turnId: 't3' })
  await $.tool.call(bash('ls'))
  expect((await $.classic.Stop(stop('Done.\n\nDecision needed: none.\n\n- Want me to push it?'))).block).toMatch(/ends with a question/)
  for (const [n, reply] of ['Done.\n\n**Decision needed:**\n\n- Post it to PR 12?', 'Done.\n\n**Decision needed:**\n\nWhich target should I use?', 'Decision needed:\n\nWhich target?\n\n- a\n- b?', 'Decision needed: apply this patch?\n\n```diff\n-a\n+b\n```', 'Decision needed:\n1. Post?\n\n2. Or push?', 'Decision needed:\n\n- A: do x\n  and also y\n- B?', 'Decision needed: pick one?\n\n~~~\nx\n~~~'].entries()) {
    await $.turn.start({ text: 'draft', turnId: `d${n}` })
    await $.tool.call(bash('ls'))
    expect((await $.classic.Stop(stop(reply))).block, reply).toBeUndefined()
  }
})

test('leaves a quoted question in a requested draft alone', async ($, on) => {
  toolEngine(on)
  await $.turn.start({ text: 'Draft a review comment using the source. Do not send it.', turnId: 't1' })
  await $.tool.call({ tool: 'Read', file_path: '/repo/a.ts' })
  expect((await $.classic.Stop(stop('Draft:\n\n> Could you add a regression test?'))).block).toBeUndefined()
})

test('still sends back a question that follows quoted content', async ($, on) => {
  toolEngine(on)
  await $.turn.start({ text: 'Draft a review comment using the source. Do not send it.', turnId: 't1' })
  await $.tool.call({ tool: 'Read', file_path: '/repo/a.ts' })
  expect((await $.classic.Stop(stop('> Decision needed: add a regression test?\n\nShould I apply the fix?'))).block).toMatch(/ends with a question/)
})

test('sends a check once per Stop chain even when the continuation starts a turn with text', async ($, on) => {
  toolEngine(on)
  await $.turn.start({ text: 'fix it', turnId: 't1' })
  await $.tool.call(bash('ls'))
  expect((await $.classic.Stop(stop('Apply?'))).block).toMatch(/ends with a question/)
  await $.turn.start({ text: 'Stop hook feedback: …', turnId: 't1-continue' })
  await $.tool.call(bash('ls'))
  expect((await $.classic.Stop(stop('Apply?', true))).block).toBeUndefined()
})

test('leaves an open item phrased as a question alone', async ($, on) => {
  toolEngine(on)
  await $.turn.start({ text: 'fix it', turnId: 't1' })
  await $.tool.call(bash('ls'))
  expect((await $.classic.Stop(stop('Done.\n\nOpen:\n- does it work on Linux?'))).block).toBeUndefined()
  await $.turn.start({ text: 'fix it', turnId: 't2' })
  await $.tool.call(bash('ls'))
  expect((await $.classic.Stop(stop('Done.\n\nNext:\n- want me to push?'))).block).toMatch(/ends with a question/)
})
