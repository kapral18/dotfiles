import type { On } from 'claude-code'
import { expect, test } from 'claude-code/testing'

const ran = (stdout: string, exitCode = 0) => ({ exitCode, stdout, stderr: '', isStdoutTruncated: false, isStderrTruncated: false })
const edit = (file_path: string) => ({ tool: 'Edit', file_path, old_string: 'a', new_string: 'b' }) as const
const stop = (last_assistant_message: string, stop_hook_active = false) => ({ stop_hook_active, last_assistant_message })
// A subagent still in flight at Stop, which pauses the turn.
const running = [{ id: 'a1', type: 'subagent', status: 'running', description: 'review' }]

// The engine beneath the plugin; `tree` is what each working-tree snapshot reads.
const engine = (on: On, tree: string[] = []) => {
  on('turn.start', ($, e) => ({ turnId: e.turnId }))
  on('process.run', () => ({ value: tree[0] === 'fail' ? ran('', 3) : ran(tree.shift() ?? 'same') }))
  on('tool.call', ($, e) => (e.tool === 'Edit' && e.file_path.endsWith('denied.ts') ? { deny: 'no' } : { result: {} as never }))
  on('classic.Stop', () => ({}))
  on('settings.read', () => ({ value: {} }))
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

test('accepts a bold Checked header without a colon, but not a sentence that starts with Checked', async ($, on) => {
  engine(on)
  for (const header of ['**Checked**', '**Checked** (3 items):', '+ Checked:']) {
    await $.turn.start({ text: 'fix it', turnId: header })
    await $.tool.call(edit('/repo/a.ts'))
    expect((await $.classic.Stop(stop(`Done.\n\n${header}\n  - tests pass [C1]`))).block).toBeUndefined()
  }
  await $.turn.start({ text: 'again', turnId: 't2' })
  await $.tool.call(edit('/repo/a.ts'))
  expect((await $.classic.Stop(stop('Done.\n\nChecked it by hand.'))).block).toMatch(/no `Checked:` list/)
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

test('requires a Checked report outside quoted or fenced examples', async ($, on) => {
  engine(on)
  const examples = ['> Checked:\n> - tests passed', '```\nChecked:\n- tests passed\n```', '~~~\nChecked:\n- tests passed', '````markdown\n```\nChecked: none\n```\n````', '~~~\n~~~ language\nChecked: none\n~~~~', '```\n    ```\nChecked: none\n```']
  for (const [i, answer] of examples.entries()) {
    await $.turn.start({ text: 'fix it', turnId: `example-${i}` })
    await $.tool.call(edit('/repo/a.ts'))
    expect((await $.classic.Stop(stop(answer))).block).toMatch(/no `Checked:` list/)
  }
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

test('waits out a pause on a subagent, then checks the answer that ends the turn', async ($, on) => {
  engine(on)
  await $.turn.start({ text: 'fix it', turnId: 't1' })
  await $.tool.call(edit('/repo/a.ts'))
  expect((await $.classic.Stop({ ...stop('Reviewers are running.'), background_tasks: running })).block).toBeUndefined()
  // The task notice continues the turn; a background shell task alone does not pause it.
  await $.turn.start({ text: '<task-notification>\n<task-id>a1</task-id>', turnId: 'notice' })
  const shell = [{ id: 's1', type: 'shell', status: 'running', description: 'dev server' }]
  expect((await $.classic.Stop({ ...stop('Done.'), background_tasks: shell })).block).toMatch(/no `Checked:` list/)
  // A notice after an ended turn starts a new one, with no edits.
  await $.turn.start({ text: '<task-notification>\n<task-id>s1</task-id>', turnId: 'later' })
  expect((await $.classic.Stop(stop('The server stopped.'))).block).toBeUndefined()
})

test('a typed prompt during a pause starts a new turn', async ($, on) => {
  engine(on)
  await $.turn.start({ text: 'fix it', turnId: 't1' })
  await $.tool.call(edit('/repo/a.ts'))
  await $.classic.Stop({ ...stop('Reviewers are running.'), background_tasks: running })
  await $.turn.start({ text: 'what is left?', turnId: 't2' })
  expect((await $.classic.Stop(stop('Nothing.'))).block).toBeUndefined()
})

test('does not guess when the snapshot fails outside a git repo', async ($, on) => {
  engine(on, ['fail'])
  await $.turn.start({ text: 'touch it', turnId: 't1' })
  await $.tool.call({ tool: 'Bash', command: 'touch x' })
  expect((await $.classic.Stop(stop('Done.'))).block).toBeUndefined()
})

test('leaves an answer another Stop hook sends back, such as /goal, and checks the answer that ends the turn', async ($, on) => {
  let isGoalMet = false
  on('turn.start', ($, e) => ({ turnId: e.turnId }))
  on('process.run', () => ({ value: ran('same') }))
  on('tool.call', () => ({ result: {} as never }))
  on('classic.Stop', () => (isGoalMet ? {} : { block: 'goal not met yet' }))
  on('settings.read', () => ({ value: {} }))
  await $.turn.start({ text: 'fix', turnId: 't1' })
  await $.tool.call(edit('/repo/a.ts'))
  expect((await $.classic.Stop(stop('Still working.'))).block).toBe('goal not met yet')
  // The goal's continuation keeps stop_hook_active set, and it is no send-back of this mod.
  expect((await $.classic.Stop(stop('Still working.', true))).block).toBe('goal not met yet')
  isGoalMet = true
  const block = (await $.classic.Stop(stop('Fixed it. Want me to push?', true))).block
  expect(block).toMatch(/no `Checked:` list[\s\S]*ends with a question/)
  // One reminder to answer the user, last, after every message.
  expect(block?.match(/Your reply replaces your last answer/g)).toHaveLength(1)
  expect(block).toMatch(/Your reply replaces your last answer[^\n]*$/)
  expect((await $.classic.Stop(stop('Fixed it. Want me to push?', true))).block).toBeUndefined()
})

// The engine beneath the question checks: every tool call succeeds and the tree never changes.
const toolEngine = (on: On) => {
  on('turn.start', ($, e) => ({ turnId: e.turnId }))
  on('process.run', () => ({ value: ran('same') }))
  on('tool.call', () => ({ result: {} as never }))
  on('classic.Stop', () => ({}))
  on('settings.read', () => ({ value: {} }))
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
  // A send-back continues inside the turn with no turn.start; its Stop carries stop_hook_active.
  await $.tool.call(bash('ls'))
  expect((await $.classic.Stop(stop('Apply?', true))).block).toBeUndefined()
  await $.turn.start({ text: 'fix it, and ask me before you push', turnId: 't2' })
  await $.tool.call(edit('/repo/a.ts'))
  expect((await $.classic.Stop(stop('Done.'))).block).toMatch(/no `Checked:` list/)
  await $.tool.call(bash('ls'))
  expect((await $.classic.Stop(stop('Checked:\n- a.ts:1 holds it\n\nPush it?', true))).block).toBeUndefined()
})

test('sends a tool-using turn back once when the reply ends with a question', async ($, on) => {
  toolEngine(on)
  await $.turn.start({ text: 'look', turnId: 't1' })
  expect((await $.classic.Stop(stop('Which file do you mean?'))).block).toBeUndefined()
  await $.tool.call(bash('ls'))
  const sentBack = (await $.classic.Stop(stop('I found two options.\n\nShould I apply the fix?'))).block
  expect(sentBack).toMatch(/ends with a question/)
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

test('WHEN a decision label is a list item SHOULD keep its question', async ($, on) => {
  toolEngine(on)
  await $.turn.start({ text: 'draft the comment', turnId: 't1' })
  await $.tool.call(bash('ls'))
  expect((await $.classic.Stop(stop('+ Decision needed:\n  - [S1] Post the comment?'))).block).toBeUndefined()
})

test('WHEN an Open label is a list item SHOULD keep its question', async ($, on) => {
  toolEngine(on)
  await $.turn.start({ text: 'fix it', turnId: 't1' })
  await $.tool.call(bash('ls'))
  expect((await $.classic.Stop(stop('+ Open:\n  - Does it work on Linux?'))).block).toBeUndefined()
})

test('WHEN a report label is indented after prose SHOULD keep its open question', async ($, on) => {
  toolEngine(on)
  await $.turn.start({ text: 'fix it', turnId: 't1' })
  await $.tool.call(bash('ls'))
  expect((await $.classic.Stop(stop('Done.\n\n  + Open:\n    - Does it work on Linux?'))).block).toBeUndefined()
})

test('WHEN a list decision label says none SHOULD reject an unrelated question', async ($, on) => {
  toolEngine(on)
  await $.turn.start({ text: 'fix it', turnId: 't1' })
  await $.tool.call(bash('ls'))
  expect((await $.classic.Stop(stop('+ Decision needed: none.\n\n- Want me to push?'))).block).toMatch(/ends with a question/)
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

test('leaves an open item phrased as a question alone', async ($, on) => {
  toolEngine(on)
  await $.turn.start({ text: 'fix it', turnId: 't1' })
  await $.tool.call(bash('ls'))
  expect((await $.classic.Stop(stop('Done.\n\nOpen:\n- does it work on Linux?'))).block).toBeUndefined()
  await $.turn.start({ text: 'fix it', turnId: 't2' })
  await $.tool.call(bash('ls'))
  expect((await $.classic.Stop(stop('Done.\n\nNext:\n- want me to push?'))).block).toMatch(/ends with a question/)
})

test('sends back work parked under a heading the report has no slot for, once per turn', async ($, on) => {
  toolEngine(on)
  let n = 0
  const fresh = async (text = 'fix it') => {
    await $.turn.start({ text, turnId: `t${n++}` })
    await $.tool.call(bash('ls'))
  }
  await $.turn.start({ text: 'fix it', turnId: 'quiet' })
  expect((await $.classic.Stop(stop('Done.\n\nKnown gaps:\n- did not rerun make check'))).block).toBeUndefined()
  for (const header of ['Known gaps:', '**Known gaps**', '**Known gaps:**', '## Next steps', 'Next step:', 'Next:', '**Next:**', 'Follow-ups (later):', 'TODOs:', 'Unverified:', 'Suggested next steps:']) {
    await fresh()
    const block = (await $.classic.Stop(stop(`Done.\n\n${header}\n- rerun make check`))).block
    expect(block, header).toMatch(new RegExp('lists work under `' + header.replace(/[*()]/g, '\\$&') + '`'))
  }
  for (const message of [
    'Known gaps: none, but make check was not rerun',
    'Known gaps:\n\nNone of the tests were rerun on Linux.',
    'Known gaps: nothing was rerun on Linux',
    'Next steps:\n- None of these block, but rerun make check',
    'Known gaps:\n- none\n- rerun make check',
  ]) {
    await fresh()
    expect((await $.classic.Stop(stop(message))).block, message).toMatch(/lists work under/)
  }
  expect((await $.classic.Stop(stop('Done.\n\nKnown gaps:\n- rerun make check', true))).block).toBeUndefined()
  for (const message of [
    'Done.\n\nOpen:\n- commit: needs your request (§5)',
    'Done.\n\nProposed:\n- split the parser',
    'The known gaps in the old SOP caused this.',
    'Known gaps: none.',
    'Known gaps:\n- none',
    '**Known gaps:** none',
    'Known gaps:\n\n- _none_',
    'Checked:\n- Known gaps: removed from AGENTS.md:83\n- Remaining: 0 failures\n* Remaining: 0 warnings',
    'Remaining: 0 failures',
    'Pending: CI green on run 123',
    'Known gaps:\n1. none',
    'Known gaps: — none',
    'Next: I ran make check and it passed.',
    'Draft:\n\n> Known gaps:\n> - none',
    'Done.\n\n```md\nNext steps:\n```',
  ]) {
    await fresh()
    expect((await $.classic.Stop(stop(message))).block, message).toBeUndefined()
  }
  for (const text of [
    "what's left on this PR? list the next steps",
    'what’s left?',
    'hand off to codex',
    'Fix the bug in calc.py so add returns the sum. End your answer with a "Known gaps:" list that says you did not run python3 -c "from calc import add; print(add(2,3))".',
    'Add a Next steps section for the reviewer.',
  ]) {
    await fresh(text)
    expect((await $.classic.Stop(stop('Next steps:\n- rebase onto main'))).block, text).toBeUndefined()
  }
  for (const text of ['fix the remaining tests', 'fix the bug which left the tests failing', 'update the list so nothing is left out']) {
    await fresh(text)
    expect((await $.classic.Stop(stop('Done.\n\nNext steps:\n- rerun make check'))).block, text).toMatch(/lists work under/)
  }
})

test('sends every finding in one send-back, then none for the rest of the turn', async ($, on) => {
  toolEngine(on)
  await $.turn.start({ text: 'fix it', turnId: 't1' })
  await $.tool.call(edit('/repo/a.ts'))
  const block = (await $.classic.Stop(stop('Done.\n\nNext steps:\n- rerun make check\n\nShould I push it?'))).block ?? ''
  expect(block).toMatch(/no `Checked:` list[\s\S]*lists work under `Next steps:`[\s\S]*ends with a question[\s\S]*Your reply replaces your last answer[^\n]*$/)
  // A later Stop in the same turn, even one that starts a new Stop chain, goes through.
  expect((await $.classic.Stop(stop('Done.\n\nKnown gaps:\n- x'))).block).toBeUndefined()
  await $.turn.start({ text: 'next request', turnId: 't2' })
  await $.tool.call(bash('ls'))
  expect((await $.classic.Stop(stop('Want me to push?'))).block).toMatch(/ends with a question/)
})

test('a continuation after a send-back keeps the turn and sends it back only once', async ($, on) => {
  toolEngine(on)
  await $.turn.start({ text: 'fix it', turnId: 't1' })
  await $.tool.call(edit('/repo/a.ts'))
  expect((await $.classic.Stop(stop('Done.'))).block).toMatch(/no `Checked:` list/)
  await $.tool.call(bash('ls'))
  expect((await $.classic.Stop(stop('Done.', true))).block).toBeUndefined()
})

test('an empty-text turn.start after a pause keeps the turn\'s edits', async ($, on) => {
  toolEngine(on)
  await $.turn.start({ text: 'fix it', turnId: 't1' })
  await $.tool.call(edit('/repo/a.ts'))
  expect((await $.classic.Stop({ ...stop('Reviewers are running.'), background_tasks: running })).block).toBeUndefined()
  await $.turn.start({ text: '', turnId: 'resume' })
  expect((await $.classic.Stop(stop('Done.'))).block).toMatch(/no `Checked:` list/)
})

test('checks the next answer after an engine nudge that follows a passed Stop', async ($, on) => {
  toolEngine(on)
  await $.turn.start({ text: 'fix it again', turnId: 't2' })
  await $.tool.call(bash('ls'))
  expect((await $.classic.Stop(stop('Done.'))).block).toBeUndefined()
  // A nudge (brief mode, a reply gate, a /goal check-in) continues the turn with stop_hook_active; no send-back came before it.
  await $.tool.call(edit('/repo/a.ts'))
  expect((await $.classic.Stop(stop('Fixed it. Want me to push?', true))).block).toMatch(/no `Checked:` list[\s\S]*ends with a question/)
  expect((await $.classic.Stop(stop('Fixed it. Want me to push?', true))).block).toBeUndefined()
})

test('an empty-text turn that follows no pause is a new turn, also after an interrupted send-back', async ($, on) => {
  toolEngine(on)
  await $.turn.start({ text: 'fix it', turnId: 't1' })
  await $.tool.call(edit('/repo/a.ts'))
  expect((await $.classic.Stop(stop('Done.\n\nChecked:\n- a.ts:1'))).block).toBeUndefined()
  // A notice with no typed prompt: the last turn's edit does not carry over.
  await $.turn.start({ text: '', turnId: 'n1' })
  expect((await $.classic.Stop(stop('Noted.'))).block).toBeUndefined()
  // The previous turn's send-back does not silence the next one.
  await $.turn.start({ text: 'fix it', turnId: 't2' })
  await $.tool.call(edit('/repo/a.ts'))
  expect((await $.classic.Stop(stop('Done.'))).block).toMatch(/no `Checked:` list/)
  // The continuation is interrupted, so no Stop follows; an idle notice then starts a new turn with its own checks.
  await $.turn.start({ text: '', turnId: 'n2' })
  await $.tool.call(edit('/repo/c.ts'))
  expect((await $.classic.Stop(stop('Edited. Push it?'))).block).toMatch(/no `Checked:` list[\s\S]*ends with a question/)
})

test('a subagent start does not reset the main turn', async ($, on) => {
  toolEngine(on)
  await $.turn.start({ text: 'fix it', turnId: 't1' })
  await $.tool.call(edit('/repo/a.ts'))
  await $.turn.start({ text: 'review the diff', turnId: 'sub1', agentId: 'agent-1' } as never)
  expect((await $.classic.Stop(stop('Done.'))).block).toMatch(/no `Checked:` list/)
})

test('compares against the tree before the turn\'s first Bash call', async ($, on) => {
  engine(on, ['before', 'after', 'after'])
  await $.turn.start({ text: 'sed it', turnId: 't1' })
  await $.tool.call({ tool: 'Bash', command: "sed -i '' s/a/b/ a.ts" })
  await $.tool.call({ tool: 'Bash', command: 'git diff --stat' })
  expect((await $.classic.Stop(stop('Done.'))).block).toMatch(/no `Checked:` list/)
})

test('does not count a failed edit as a change', async ($, on) => {
  on('turn.start', ($, e) => ({ turnId: e.turnId }))
  on('process.run', () => ({ value: ran('same') }))
  on('tool.call', () => ({ result: {} as never, isError: true as const }))
  on('classic.Stop', () => ({}))
  on('settings.read', () => ({ value: {} }))
  await $.turn.start({ text: 'fix it', turnId: 't1' })
  await $.tool.call(edit('/repo/a.ts'))
  expect((await $.classic.Stop(stop('Could not edit it.'))).block).toBeUndefined()
})

test('checks the first Stop it sees even with stop_hook_active set: a managed hook blocked the one before', async ($, on) => {
  toolEngine(on)
  // A Stop that passes, then an interrupt: the next turn starts fresh.
  await $.turn.start({ text: 'look', turnId: 't1' })
  await $.tool.call(bash('ls'))
  expect((await $.classic.Stop(stop('Looked.'))).block).toBeUndefined()
  await $.turn.start({ text: 'fix it', turnId: 't2' })
  await $.tool.call(edit('/repo/a.ts'))
  // A managed-settings Stop hook blocked an earlier Stop, so this mod never saw it.
  expect((await $.classic.Stop(stop('Fixed it.', true))).block).toMatch(/no `Checked:` list/)
  expect((await $.classic.Stop(stop('Fixed it.', true))).block).toBeUndefined()
})

test('an engine nudge after a paused Stop, such as a /goal check-in, is no send-back: the turn is still checked', async ($, on) => {
  toolEngine(on)
  await $.turn.start({ text: 'fix it', turnId: 't1' })
  await $.tool.call(edit('/repo/a.ts'))
  expect((await $.classic.Stop({ ...stop('Waiting.'), background_tasks: running })).block).toBeUndefined()
  expect((await $.classic.Stop({ ...stop('Still waiting.', true), background_tasks: running })).block).toBeUndefined()
  await $.turn.start({ text: '<task-notification>done</task-notification>', turnId: 'wake' })
  expect((await $.classic.Stop(stop('Done.'))).block).toMatch(/no `Checked:` list/)
})

test('after an answer passes, a later Stop in the turn needs Checked: only for later changes', async ($, on) => {
  engine(on, ['before', 'before', 'before', 'after'])
  await $.turn.start({ text: 'fix it', turnId: 't1' })
  await $.tool.call(edit('/repo/a.ts'))
  expect((await $.classic.Stop(stop('Done.\n\nChecked:\n- make check passed'))).block).toBeUndefined()
  // A re-delivery nudge (brief mode, a reply gate) sends the answer through a tool and ends with no text.
  await $.tool.call({ tool: 'Bash', command: 'git status' })
  expect((await $.classic.Stop(stop('', true))).block).toBeUndefined()
  // Work after the passed answer changes the tree, so its answer needs Checked: again.
  await $.tool.call({ tool: 'Bash', command: "sed -i '' s/a/b/ a.ts" })
  expect((await $.classic.Stop(stop('Fixed the rest.', true))).block).toMatch(/no `Checked:` list/)
})

test('after an answer passes, a background job\'s later write still counts as a change', async ($, on) => {
  engine(on, ['before', 'before', 'written'])
  await $.turn.start({ text: 'start the build', turnId: 't1' })
  await $.tool.call({ tool: 'Bash', command: 'make build &' })
  expect((await $.classic.Stop(stop('Started.\n\nChecked:\n- make build is running'))).block).toBeUndefined()
  // A /goal check-in continues the turn after the job wrote its output.
  expect((await $.classic.Stop(stop('The build finished.', true))).block).toMatch(/no `Checked:` list/)
})

// `n` words of prose, one word per line so no line reads as a question or a heading.
const filler = (n: number) => Array.from({ length: n }, (_, i) => `word${i}`).join('\n')

test('sends back an answer over the §8 word budget: 250 for a change report, 200 otherwise, lists and tables included', async ($, on) => {
  engine(on)
  await $.turn.start({ text: 'fix it', turnId: 't1' })
  await $.tool.call(edit('/repo/a.ts'))
  expect((await $.classic.Stop(stop(`Done.\n\nChecked:\n- tests pass [C1]\n${filler(246)}`))).block).toMatch(/is 251 words; .*caps this answer at 250/)
  await $.turn.start({ text: 'fix it', turnId: 't2' })
  await $.tool.call(edit('/repo/a.ts'))
  expect((await $.classic.Stop(stop(`Done.\n\nChecked:\n- tests pass [C1]\n${filler(245)}`))).block).toBeUndefined()
  await $.turn.start({ text: 'why is it slow', turnId: 't3' })
  await $.tool.call({ tool: 'Read', file_path: '/repo/a.ts' })
  expect((await $.classic.Stop(stop(`| a | b |\n| --- | --- |\n${filler(199)}`))).block).toMatch(/is 201 words; .*caps this answer at 200/)
})

test('the word budget skips fenced drafts, quotes, and tool-free answers; a prompt for detail is left to the agent', async ($, on) => {
  engine(on)
  await $.turn.start({ text: 'draft the PR body', turnId: 't1' })
  await $.tool.call({ tool: 'Read', file_path: '/repo/a.ts' })
  expect((await $.classic.Stop(stop(`Draft:\n\n\`\`\`md\n${filler(400)}\n\`\`\`\n\n> ${filler(50).replace(/\n/g, ' ')}`))).block).toBeUndefined()
  await $.turn.start({ text: 'explain it', turnId: 't2' })
  expect((await $.classic.Stop(stop(filler(400)))).block).toBeUndefined()
  await $.turn.start({ text: 'explain the flow in detail', turnId: 't3' })
  await $.tool.call({ tool: 'Read', file_path: '/repo/a.ts' })
  expect((await $.classic.Stop(stop(filler(400)))).block).toMatch(/is 400 words; .*keep the answer as it is/s)
})

// §8 exempts Markdown blocks, including their list containers and lazy quote continuations.
for (const [name, answer] of [
  ['a list contains an indented fence', `- Example:\n\n    \`\`\`ts\n    ${filler(300).replace(/\n/g, '\n    ')}\n    \`\`\``],
  ['nested lists contain a tilde fence', `- Outer\n  1. Example:\n\n      ~~~\n      ${filler(300).replace(/\n/g, '\n      ')}\n      ~~~`],
  ['a fence opens on a list marker', `- \`\`\`ts\n  ${filler(300).replace(/\n/g, '\n  ')}\n  \`\`\``],
  ['a blockquote has lazy paragraph continuations', `> Quoted.\n${filler(300)}`],
  ['a lazy quote continuation resembles a setext underline', `> Quoted.\n===\n${filler(300)}`],
  ['a list contains a lazily continued blockquote', `- Quote:\n\n  > Quoted.\n  ${filler(300).replace(/\n/g, '\n  ')}`],
]) {
  test(`WHEN ${name} SHOULD exclude its words from the budget`, async ($, on) => {
    engine(on)
    await $.turn.start({ text: 'explain', turnId: 't1' })
    await $.tool.call({ tool: 'Read', file_path: '/repo/a.ts' })
    expect((await $.classic.Stop(stop(answer))).block).toBeUndefined()
  })
}

for (const [name, answer] of [
  ['a raw HTML closing tag contains whitespace', '> <script>\n> </script >\n> Paragraph.\nShould I push?'],
  ['a valid self-closing block tag starts HTML', '> <div/>\nShould I push?'],
  ['a quoted HTML block contains a non-ASCII space line', '> <div>\n> \u00a0\n> Paragraph.\nShould I push?'],
  ['an unquoted HTML attribute has a non-ASCII value', '> <a x=\u00a0>\nShould I push?'],
  ['an empty bullet has trailing spaces before a fence', '-   \n  ```\nShould I push?'],
  ['an empty ordered item has trailing spaces before a fence', '1.   \n   ```\nShould I push?'],
  ['an empty bullet has tab padding before a fence', '-\t\n  ```\nShould I push?'],
  ['a nonempty item continues after a blank line', '- Item\n\n  ```\nShould I push?'],
  ['an empty sibling list item ends a quoted paragraph', '> - Item\n> -\nShould I push?'],
  ['an empty list marker ends a quote', '> Quoted.\n-\nShould I push?'],
  ['an empty ordered list marker ends a quote', '> Quoted.\n2.\nShould I push?'],
  ['an ordered list starting at two ends a quote', '> Quoted.\n2. Should I push?'],
  ['an ordered marker continues a paragraph', 'Intro\n2. > Should I push?'],
  ['a leading-zero ordered list interrupts a quote', '> Quoted.\n01. Should I push?'],
  ['a quoted HTML block has content', '> <div>\n> html\nShould I push?'],
  ['a quoted HTML custom element starts a block', '> <custom-tag>\nShould I push?'],
  ['a quoted complete HTML tag starts a block', '> <a>\nShould I push?'],
  ['a quoted HTML comment has content', '> <!--\n> comment\nShould I push?'],
  ['a quoted processing instruction has content', '> <?\n> instruction\nShould I push?'],
  ['a quoted CDATA block has content', '> <![CDATA[\n> data\nShould I push?'],
  ['a quoted declaration has content', '> <!DOCTYPE\n> declaration\nShould I push?'],
  ['a quoted raw HTML tag has content', '> <script>\n> script\nShould I push?'],
  ['a quoted HTML attribute contains a closing angle', '> <a title=">">\nShould I push?'],
]) {
  test(`WHEN ${name} SHOULD check the outside question`, async ($, on) => {
    engine(on)
    await $.turn.start({ text: 'explain', turnId: 't1' })
    await $.tool.call({ tool: 'Read', file_path: '/repo/a.ts' })
    expect((await $.classic.Stop(stop(answer))).block).toMatch(/ends with a question/)
  })
}

for (const [name, answer] of [
  ['a quoted HTML block ends at a blank line', `> <div>\n> html\n>\n> Paragraph.\n${filler(300)}`],
  ['a quoted raw HTML block closes', `> <script>\n> code\n> </script>\n> Paragraph.\n${filler(300)}`],
  ['a quoted HTML comment closes', `> <!-- comment -->\n> Paragraph.\n${filler(300)}`],
  ['an empty multi-digit ordered item contains a fence', `10.   \n    \`\`\`\n    ${filler(300).replace(/\n/g, '\n    ')}\n    \`\`\``],
  ['a blank line ends an empty item before a root fence', `- \n\n  \`\`\`\n${filler(300)}\n\`\`\``],
  ['a malformed block tag has a slash after its name', `> <div/foo>\n${filler(300)}`],
  ['a malformed closing block tag has a slash after its name', `> </div/foo>\n${filler(300)}`],
  ['a malformed self-closing block tag has a space after its slash', `> <div/ >\n${filler(300)}`],
  ['an HTML tag uses non-ASCII spacing', `> <a\u00a0b>\n${filler(300)}`],
  ['a closing HTML tag uses non-ASCII spacing', `> </a\u00a0>\n${filler(300)}`],
  ['a quoted paragraph contains a non-ASCII space line', `> Paragraph.\n\u00a0\n${filler(300)}`],
  ['an invalid opening HTML tag is quoted paragraph text', `> <custom_tag>\n${filler(300)}`],
  ['an invalid closing HTML tag is quoted paragraph text', `> </custom_tag>\n${filler(300)}`],
  ['an HTML tag continues a quoted paragraph', `> Paragraph.\n> <a>\n${filler(300)}`],
]) {
  test(`WHEN ${name} SHOULD exclude the lazy quoted paragraph`, async ($, on) => {
    engine(on)
    await $.turn.start({ text: 'explain', turnId: 't1' })
    await $.tool.call({ tool: 'Read', file_path: '/repo/a.ts' })
    expect((await $.classic.Stop(stop(answer))).block).toBeUndefined()
  })
}

test('WHEN a list contains a fenced Checked label SHOULD still require a real report', async ($, on) => {
  engine(on)
  await $.turn.start({ text: 'fix', turnId: 't1' })
  await $.tool.call(edit('/repo/a.ts'))
  expect((await $.classic.Stop(stop('- Example:\n\n    ```md\n    Checked:\n    - tests passed\n    ```'))).block).toMatch(/no `Checked:` list/)
})

test('WHEN a lazy blockquote ends with a question SHOULD leave the quoted question alone', async ($, on) => {
  engine(on)
  await $.turn.start({ text: 'draft', turnId: 't1' })
  await $.tool.call({ tool: 'Read', file_path: '/repo/a.ts' })
  expect((await $.classic.Stop(stop('Draft:\n\n> Could you check\nthe regression?'))).block).toBeUndefined()
})

for (const [name, answer] of [
  ['a list fence ends by dedenting', `- \`\`\`\n  code\n${filler(201)}`],
  ['a blank line ends a lazy blockquote', `> Quoted.\nlazy continuation\n\n${filler(201)}`],
  ['a heading interrupts a lazy blockquote', `> Quoted.\n# Heading\n${filler(200)}`],
  ['a quoted fence has no lazy continuation', `> \`\`\`\n> code\n${filler(201)}`],
]) {
  test(`WHEN ${name} SHOULD count the following prose`, async ($, on) => {
    engine(on)
    await $.turn.start({ text: 'explain', turnId: 't1' })
    await $.tool.call({ tool: 'Read', file_path: '/repo/a.ts' })
    expect((await $.classic.Stop(stop(answer))).block).toMatch(/is 201 words; .*caps this answer at 200/)
  })
}

test('a turn woken by a background job keeps the typed prompt\'s request for a list', async ($, on) => {
  engine(on)
  await $.turn.start({ text: 'run the benchmark and list the next steps', turnId: 't1' })
  await $.tool.call({ tool: 'Read', file_path: '/repo/a.ts' })
  expect((await $.classic.Stop(stop('Started the benchmark in the background.'))).block).toBeUndefined()
  await $.turn.start({ text: '<task-notification>done</task-notification>', turnId: 't2' })
  expect((await $.classic.Stop(stop('Benchmark done.\n\nNext steps:\n- tune the cache'))).block).toBeUndefined()
})

test('a change with no Checked: list gets the 250-word change budget, so 220 words only miss the list', async ($, on) => {
  engine(on)
  await $.turn.start({ text: 'fix it', turnId: 't1' })
  await $.tool.call(edit('/repo/a.ts'))
  const block = (await $.classic.Stop(stop(filler(220)))).block
  expect(block).toMatch(/no `Checked:` list/)
  expect(block).not.toMatch(/caps this answer/)
})
