import type { On } from 'claude-code'
import { expect, test } from 'claude-code/testing'

const ran = (stdout: string, exitCode = 0) => ({ exitCode, stdout, stderr: '', isStdoutTruncated: false, isStderrTruncated: false })
const edit = (file_path: string) => ({ tool: 'Edit', file_path, old_string: 'a', new_string: 'b' }) as const
const stop = (last_assistant_message: string) => ({ stop_hook_active: false, last_assistant_message })

// The engine beneath the plugin: `,task hook` answers each event from `answers`; every call is recorded.
const engine = (on: On, answers: Record<string, unknown> = {}, below: { block?: string } = {}, toolResult: object = {}, terminal: { deny?: string; isError?: boolean } = {}) => {
  const calls: { event: string; input: Record<string, unknown> }[] = []
  on('session.cwd', () => ({ value: '/repo' }))
  on('session.id', () => ({ value: 's1' }))
  on('process.run', ($, e) => {
    const [, , event = '', , , , json = '{}'] = e.argv
    calls.push({ event, input: JSON.parse(json) as Record<string, unknown> })
    return { value: ran(JSON.stringify(answers[event] ?? {})) }
  })
  on('tool.call', () => terminal.deny ? { deny: terminal.deny } : { result: toolResult as never, isError: terminal.isError })
  on('classic.Stop', () => below)
  return calls
}

test('refuses an edit when ,task denies it, before the edit runs', async ($, on) => {
  const calls = engine(on, { tool: { deny: 'intent-guard: no intent card' } })
  const result = await $.tool.call(edit('/repo/src/a.ts'))
  expect(result.deny).toBe('intent-guard: no intent card')
  expect(calls).toEqual([{ event: 'tool', input: { tool: 'Edit', paths: ['/repo/src/a.ts'], write: true, call_id: expect.any(String), phase: 'before', cwd: '/repo', session: 's1' } }])
})

test('adds the scope note to the edit result', async ($, on) => {
  engine(on, { tool: { note: 'intent-guard: docs/x.md is outside' } })
  const result = await $.tool.call(edit('/repo/docs/x.md'))
  expect(result.deny).toBeUndefined()
  expect(result.context).toEqual(['intent-guard: docs/x.md is outside'])
})

test('WHEN a direct write fails SHOULD settle its snapshot and preserve the error', async ($, on) => {
  const calls = engine(on, { tool: { note: 'partial write is outside' } }, {}, {}, { isError: true })
  const result = await $.tool.call(edit('/repo/notes.txt'))
  expect(result.isError).toBe(true)
  expect(calls.map(call => call.input.phase)).toEqual(['before', 'after'])
  expect(calls[1]?.input.call_id).toBe(calls[0]?.input.call_id)
  expect(result.context).toEqual(['partial write is outside'])
})

test('WHEN a later guard denies a direct write SHOULD settle its snapshot', async ($, on) => {
  const calls = engine(on, {}, {}, {}, { deny: 'blocked below' })
  const result = await $.tool.call(edit('/repo/notes.txt'))
  expect(result.deny).toBe('blocked below')
  expect(calls.map(call => call.input.phase)).toEqual(['before', 'after'])
})

test('counts other tool calls and adds the zoom-out note after they run', async ($, on) => {
  const calls = engine(on, { tool: { note: 'intent-guard: zoom out.' } })
  const result = await $.tool.call({ tool: 'Bash', command: 'ls' })
  expect(result.context).toEqual(['intent-guard: zoom out.'])
  expect(calls.map(call => call.input.phase)).toEqual(['before', 'after'])
  expect(calls[0]?.input.tool).toBe('Bash')
  expect(calls[0]?.input.call_id).toEqual(expect.any(String))
  expect(calls[1]?.input.call_id).toBe(calls[0]?.input.call_id)
})

test('attaches the card to a typed prompt and leaves slash commands alone', async ($, on) => {
  const calls = engine(on, { prompt: { context: 'Intent card for this task' } })
  on('prompt.submit', ($, e) => ({ text: e.text, context: e.context }))
  const entered = await $.prompt.submit({ text: 'add the button', asUser: true })
  expect(entered.context).toEqual(['Intent card for this task'])
  expect(calls[0]?.input.text).toBe('add the button')
  expect(calls[0]?.input.origin).toBe('human')
})

test('WHEN Bash returns a background task SHOULD retain its snapshot', async ($, on) => {
  const calls = engine(on, {}, {}, { stdout: '', stderr: '', interrupted: false, backgroundTaskId: 'job-1' })
  await $.tool.call({ tool: 'Bash', command: 'sleep 1', run_in_background: true })
  expect(calls[1]?.input).toEqual(expect.objectContaining({ phase: 'after', background: true, background_id: 'job-1' }))
})

test('WHEN Bash ends with the final response SHOULD request Stop snapshots', async ($, on) => {
  const calls = engine(on, {}, {}, { stdout: '', stderr: '', interrupted: false, backgroundTaskId: 'job-1', backgroundEndsWithFinalResponse: true })
  await $.tool.call({ tool: 'Bash', command: 'sleep 1', run_in_background: true })
  expect(calls[1]?.input).toEqual(expect.objectContaining({ background: true, background_id: 'job-1', until_stop: true }))
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

test('WHEN GetTask delivers a terminal result SHOULD complete its shell snapshot', async ($, on) => {
  const calls = engine(on, { tool: { note: 'late.txt is outside' } }, {}, { taskId: 'job-1', statusMessage: 'done', createdAt: '', lastUpdatedAt: '', status: 'cancelled' })
  await $.tool.call({ tool: 'GetTask', taskId: 'job-1' })
  expect(calls[1]?.input).toEqual(expect.objectContaining({ tool: 'Bash', phase: 'complete', background_id: 'job-1' }))
})

test('WHEN GetTask is still working SHOULD leave its snapshot pending', async ($, on) => {
  const calls = engine(on, {}, {}, { taskId: 'job-1', statusMessage: 'working', createdAt: '', lastUpdatedAt: '', status: 'working' })
  await $.tool.call({ tool: 'GetTask', taskId: 'job-1' })
  expect(calls.map(call => call.input.phase)).toEqual(['after'])
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
  on('tool.call', () => ({ result: {} as never }))
  on('classic.Stop', () => ({}))
  expect((await $.tool.call(edit('/repo/src/a.ts'))).deny).toBeUndefined()
  expect((await $.classic.Stop(stop('Done.'))).block).toBeUndefined()
})
