import type { On } from 'claude-code'
import { expect, test } from 'claude-code/testing'

const ran = (stdout: string, exitCode = 0) => ({ exitCode, stdout, stderr: '', isStdoutTruncated: false, isStderrTruncated: false })
const edit = (file_path: string) => ({ tool: 'Edit', file_path, old_string: 'a', new_string: 'b' }) as const

// The engine beneath the plugin: a repo at /repo and a fixed `affected` answer.
const engine = (on: On, affected: string, top = ran('/repo\n'), fails = { edit: false }) => {
  const argv: string[][] = []
  on('fs.exists', () => ({ value: true }))
  on('process.run', ($, e) => {
    argv.push([...e.argv])
    return { value: e.argv[0] === 'git' ? top : ran(affected) }
  })
  on('tool.call', () => (fails.edit ? { result: {} as never, isError: true as const } : { result: {} as never }))
  return argv
}

test('stops the first edit in an unmapped directory, then lets the retry through', async ($, on) => {
  engine(on, 'unmapped: src\n1 files; 1 outside every mapped area\n')
  const first = await $.tool.call(edit('/repo/src/a.ts'))
  expect(first.deny).toMatch(/src in \/repo has no behavior-map area/)
  const retry = await $.tool.call(edit('/repo/src/b.ts'))
  expect(retry.deny).toBeUndefined()
})

test('lets docs-only and test-only edits through in an unmapped directory', async ($, on) => {
  engine(on, 'unmapped: src\n')
  for (const path of ['/repo/src/README.md', '/repo/src/tests/a.py', '/repo/src/a.test.ts', '/repo/src/test_a.py']) {
    expect((await $.tool.call(edit(path))).deny).toBeUndefined()
  }
})

test('names the touched entries and areas once per session', async ($, on) => {
  engine(on, 'entry auth/login: src/a.ts\narea billing: 3 entries, check them with `show billing`; changed src/a.ts\n1 files; 0 outside every mapped area\n')
  const first = await $.tool.call(edit('/repo/src/a.ts'))
  expect(first.deny).toBeUndefined()
  expect(first.context?.join('\n')).toMatch(/touches auth\/login, billing\./)
  const second = await $.tool.call(edit('/repo/src/a.ts'))
  expect(second.context ?? []).toEqual([])
})

test('skips scratch paths and paths outside git', async ($, on) => {
  const argv = engine(on, 'unmapped: src\n', ran('', 128))
  expect((await $.tool.call(edit('/tmp/x/a.ts'))).deny).toBeUndefined()
  expect(argv).toEqual([])
  expect((await $.tool.call(edit('/elsewhere/a.ts'))).deny).toBeUndefined()
  expect(argv).toEqual([['git', 'rev-parse', '--show-toplevel']])
})

test('lets the edit through when the map command fails', async ($, on) => {
  on('fs.exists', () => ({ value: true }))
  on('process.run', ($, e) => {
    return e.argv[0] === 'git' ? { value: ran('/repo\n') } : { deny: 'spawn ,behavior-map ENOENT' }
  })
  on('tool.call', () => ({ result: {} as never }))
  expect((await $.tool.call(edit('/repo/src/a.ts'))).deny).toBeUndefined()
})

test('points a root-level or shared-directory file at a file anchor', async ($, on) => {
  engine(on, 'unmapped: .\n')
  const first = await $.tool.call(edit('/repo/Makefile'))
  expect(first.deny).toMatch(/\. in \/repo has no behavior-map area/)
  expect(first.deny).toMatch(/add it as a file anchor to the closest entry/)
})

test('judges docs and tests by the repo-relative path', async ($, on) => {
  engine(on, 'unmapped: src\n', ran('/home/tests/app\n'))
  expect((await $.tool.call(edit('/home/tests/app/src/server.ts'))).deny).toMatch(/no behavior-map area/)
  expect((await $.tool.call(edit('/home/tests/app/requirements.txt'))).deny).toBeUndefined()
})

test('stops a directory again after /clear', async ($, on) => {
  engine(on, 'unmapped: src\n')
  on('session.end', () => ({ sessionId: 's1' }))
  expect((await $.tool.call(edit('/repo/src/a.ts'))).deny).toBeDefined()
  await $.session.end({ reason: 'clear', sessionId: 's1', resume: { id: 's1' } })
  expect((await $.tool.call(edit('/repo/src/a.ts'))).deny).toBeDefined()
})

test('keeps the note for the next edit when an edit fails', async ($, on) => {
  const fails = { edit: true }
  engine(on, 'entry auth/login: src/a.ts\n', ran('/repo\n'), fails)
  expect((await $.tool.call(edit('/repo/src/a.ts'))).context ?? []).toEqual([])
  fails.edit = false
  expect((await $.tool.call(edit('/repo/src/a.ts'))).context?.join('\n')).toMatch(/touches auth\/login/)
})

test('adds no Stop feedback when read-only Bash runs beside older unmapped code', async ($, on) => {
  on('turn.start', ($, e) => ({ turnId: e.turnId }))
  on('process.run', ($, e) => ({
    value: ran(e.argv[0] === 'git' ? '/repo\n' : e.argv[0] === 'sh' ? 'app/slug.py\n' : 'unmapped: app\n'),
  }))
  on('tool.call', () => ({ result: {} as never }))
  on('classic.Stop', () => ({}))
  await $.turn.start({ text: 'check status without changing files', turnId: 't1' })
  await $.tool.call({ tool: 'Bash', command: 'git status --short' })
  const result = await $.classic.Stop({ stop_hook_active: false, last_assistant_message: 'The working tree has changes.' })
  expect(result.block).toBeUndefined()
  expect(result.additionalContext).toBeUndefined()
})
