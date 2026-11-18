import type { On } from 'claude-code'
import { expect, test } from 'claude-code/testing'

const ran = (stdout: string, exitCode = 0) => ({ exitCode, stdout, stderr: '', isStdoutTruncated: false, isStderrTruncated: false })
const stop = (last_assistant_message: string) => ({ stop_hook_active: false, last_assistant_message })

// The engine beneath the plugin: `,task hook` answers each event from `answers`; every call is recorded.
const engine = (on: On, answers: Record<string, unknown> = {}, below: { block?: string } = {}) => {
  const calls: { event: string; input: Record<string, unknown> }[] = []
  on('session.cwd', () => ({ value: '/repo' }))
  on('session.id', () => ({ value: 's1' }))
  on('process.run', ($, e) => {
    const [, , event = '', , , , json = '{}'] = e.argv
    calls.push({ event, input: JSON.parse(json) as Record<string, unknown> })
    return { value: ran(JSON.stringify(answers[event] ?? {})) }
  })
  on('classic.Stop', () => below)
  return calls
}

test('attaches the card to a typed prompt and leaves slash commands alone', async ($, on) => {
  const calls = engine(on, { prompt: { context: 'Intent card for this task' } })
  on('prompt.submit', ($, e) => ({ text: e.text, context: e.context }))
  const entered = await $.prompt.submit({ text: 'add the button', asUser: true })
  expect(entered.context).toEqual(['Intent card for this task'])
  expect(calls[0]?.input.text).toBe('add the button')
  expect(calls[0]?.input.origin).toBe('human')
})

for (const status of ['completed', 'failed', 'killed']) {
  test(`WHEN a shell notification is ${status} SHOULD complete the original snapshot`, async ($, on) => {
    const calls = engine(on, { tool: { note: 'late.txt is outside' } })
    on('prompt.submit', ($, e) => ({ text: e.text, context: e.context }))
    const result = await $.prompt.submit({ text: `<task-notification>\n<task-id>job-1</task-id>\n<tool-use-id>bash-call</tool-use-id>\n<output-file>/tmp/out</output-file>\n<status>${status}</status>\n<summary>Shell ended</summary>\n</task-notification>`, wait: false, origin: { kind: 'task-notification' } })
    expect(result.context).toEqual(['late.txt is outside'])
    expect(calls).toEqual([{ event: 'tool', input: { tool: 'Bash', phase: 'complete', call_id: 'bash-call', background_id: 'job-1', cwd: '/repo', session: 's1' } }])
  })
}

test('WHEN a background check-in has no terminal status SHOULD leave snapshots pending', async ($, on) => {
  const calls = engine(on)
  on('prompt.submit', ($, e) => ({ text: e.text }))
  await $.prompt.submit({ text: '<task-notification>\n<task-id>job-1</task-id>\n<tool-use-id>bash-call</tool-use-id>\n<summary>Still running</summary>\n</task-notification>', wait: false, origin: { kind: 'task-notification' } })
  expect(calls).toEqual([])
})

test('WHEN a person types notification markup SHOULD treat it as a prompt', async ($, on) => {
  const calls = engine(on)
  on('prompt.submit', ($, e) => ({ text: e.text }))
  await $.prompt.submit({ text: '<task-notification>\n<task-id>job-1</task-id>\n<tool-use-id>bash-call</tool-use-id>\n<status>completed</status>\n</task-notification>', wait: false, origin: { kind: 'composer' } })
  expect(calls.map(call => call.event)).toEqual(['prompt'])
})

test('sends the stop back with the ,task block, after a block from below', async ($, on) => {
  engine(on, { stop: { block: 'intent-guard: the task is not done' } })
  expect((await $.classic.Stop(stop('Done.'))).block).toBe('intent-guard: the task is not done')
})

test('lets another hook block first and waits for running subagents', async ($, on) => {
  const calls = engine(on, { stop: { block: 'intent-guard: open items' } }, { block: 'reviewer: fix it' })
  expect((await $.classic.Stop(stop('Done.'))).block).toBe('reviewer: fix it')
  expect(calls).toEqual([])
})

test('waits for a subagent still in flight', async ($, on) => {
  const calls = engine(on, { stop: { block: 'intent-guard: open items' } })
  const subagent = [{ id: 'a1', type: 'subagent', status: 'running', description: 'search' }] as const
  expect((await $.classic.Stop({ ...stop('Waiting.'), background_tasks: subagent })).block).toBeUndefined()
  expect(calls).toEqual([])
})

test('goes on unguarded when ,task fails', async ($, on) => {
  on('session.cwd', () => ({ value: '/repo' }))
  on('session.id', () => ({ value: 's1' }))
  on('process.run', () => ({ value: ran('', 127) }))
  on('classic.Stop', () => ({}))
  expect((await $.classic.Stop(stop('Done.'))).block).toBeUndefined()
})
