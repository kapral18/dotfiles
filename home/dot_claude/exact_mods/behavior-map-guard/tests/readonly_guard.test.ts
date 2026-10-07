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

// The engine beneath the Stop check: `changed` is the working tree's changed paths.
const stopEngine = (on: On, changed: string, affected: string, below: { block?: string } = {}) => {
  const argv: string[][] = []
  on('turn.start', ($, e) => ({ turnId: e.turnId }))
  on('fs.exists', () => ({ value: true }))
  on('process.run', ($, e) => {
    argv.push([...e.argv])
    if (e.argv[0] === 'git') return { value: ran('/repo\n') }
    if (e.argv[0] === 'sh') return { value: ran(changed) }
    return { value: ran(affected) }
  })
  on('tool.call', () => ({ result: {} as never }))
  on('classic.Stop', () => below)
  return argv
}
const bash = (command: string) => ({ tool: 'Bash', command, description: 'test' }) as const
const stop = (stop_hook_active = false) => ({ stop_hook_active, last_assistant_message: 'Done.' })

test('sends a turn back once when Bash changed code in an unmapped directory', async ($, on) => {
  const argv = stopEngine(on, 'app/slug.py\napp/cli.py\nREADME.md\ntests/test_slug.py\n', 'unmapped: app\n2 files; 2 outside every mapped area\n')
  await $.turn.start({ text: 'add slug', turnId: 't1' })
  await $.tool.call(bash("cat > app/slug.py <<'EOF'\nx\nEOF"))
  expect((await $.classic.Stop(stop())).block).toMatch(/changed code in app in \/repo, which has no behavior-map area/)
  expect(argv.find(args => args[0] === ',behavior-map')).toEqual([',behavior-map', 'affected', 'app/slug.py', 'app/cli.py'])
  expect((await $.classic.Stop(stop())).block).toBeUndefined()
})

test('passes a turn that ran no tool, a re-prompt, and docs or test changes', async ($, on) => {
  stopEngine(on, 'README.md\ntests/test_a.py\n', 'unmapped: app\n')
  await $.turn.start({ text: 'explain', turnId: 't1' })
  expect((await $.classic.Stop(stop())).block).toBeUndefined()
  await $.tool.call(bash('ls'))
  expect((await $.classic.Stop(stop(true))).block).toBeUndefined()
  expect((await $.classic.Stop(stop())).block).toBeUndefined()
})

test('passes when the changed code is mapped', async ($, on) => {
  stopEngine(on, 'app/slug.py\n', 'area app: 2 entries, check them with `show app`; changed app/slug.py\n1 files; 0 outside every mapped area\n')
  await $.turn.start({ text: 'add slug', turnId: 't1' })
  await $.tool.call(bash('touch app/slug.py'))
  expect((await $.classic.Stop(stop())).block).toBeUndefined()
})

test('adds its message to a block from below', async ($, on) => {
  stopEngine(on, 'app/slug.py\n', 'unmapped: app\n', { block: 'other gate' })
  await $.turn.start({ text: 'add slug', turnId: 't1' })
  await $.tool.call(bash('touch app/slug.py'))
  expect((await $.classic.Stop(stop())).block).toMatch(/^other gate\n\n.*no behavior-map area/s)
})

test('does not repeat a directory the edit check already stopped', async ($, on) => {
  stopEngine(on, 'app/slug.py\n', 'unmapped: app\n')
  await $.turn.start({ text: 'add slug', turnId: 't1' })
  expect((await $.tool.call(edit('/repo/app/slug.py'))).deny).toMatch(/no behavior-map area/)
  expect((await $.classic.Stop(stop())).block).toBeUndefined()
})
