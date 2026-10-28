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

const bash = (on: On, status: string, newer: string, affected: string, top = '/repo\n') => {
  const argv: string[][] = []
  on('fs.exists', () => ({ value: true }))
  on('process.run', ($, e) => {
    argv.push([...e.argv])
    const [command, first] = e.argv
    if (command === 'sh') return { value: ran('/tmp/marker\n') }
    if (command === 'git') return { value: ran(first === 'rev-parse' ? top : status) }
    if (command === 'find') return { value: ran(newer, 1) }
    return { value: ran(command === 'rm' ? '' : affected) }
  })
  on('tool.call', () => ({ result: {} as never }))
  return argv
}

test('notes unmapped Bash writes once without allowing the first Edit there', async ($, on) => {
  bash(on, ' M src/a.ts\0', './src/a.ts\n', 'unmapped: src\n1 files; 1 outside every mapped area\n')
  expect((await $.tool.call({ tool: 'Bash', command: 'echo x > src/a.ts' })).context?.join('\n')).toMatch(/changed code in src/)
  expect((await $.tool.call({ tool: 'Bash', command: 'echo y > src/a.ts' })).context ?? []).toEqual([])
  expect((await $.tool.call(edit('/repo/src/b.ts'))).deny).toMatch(/src in \/repo has no behavior-map area/)
})

test('gives overlapping Bash calls their own markers', async ($, on) => {
  let made = 0
  let release = () => {}
  const gate = new Promise<void>(resolve => {
    release = resolve
  })
  const argv: string[][] = []
  on('process.run', ($, e) => {
    argv.push([...e.argv])
    const [command, first] = e.argv
    if (command === 'sh') return { value: ran(`/tmp/m${++made}\n`) }
    if (command === 'git') return { value: ran(first === 'rev-parse' ? '/repo\n' : ' M src/a.ts\0') }
    if (command === 'find') return { value: ran('./src/a.ts\n', 1) }
    return { value: ran('') }
  })
  on('tool.call', { tool: 'Bash' }, async ($, e) => {
    if (e.command.includes('slow')) await gate
    return { result: {} as never }
  })
  const slow = $.tool.call({ tool: 'Bash', command: 'echo slow > src/a.ts' })
  await $.tool.call({ tool: 'Bash', command: 'echo fast > src/b.ts' })
  release()
  await slow
  expect(argv.filter(args => args[0] === 'find').map(args => args[args.indexOf('-cnewer') + 1])).toEqual(['/tmp/m2', '/tmp/m1'])
  expect(argv.filter(args => args[0] === 'rm').map(args => args.at(-1))).toEqual(['/tmp/m2', '/tmp/m1'])
})

test('reads a rename by its new path and skips the old one', async ($, on) => {
  const argv = bash(on, 'R  src/new.ts\0old/gone.ts\0 R src/b.ts\0README.md\0?? -dash.ts\0', './src/new.ts\n', 'unmapped: src\n')
  await $.tool.call({ tool: 'Bash', command: 'git mv old/gone.ts src/new.ts' })
  const find = argv.find(args => args[0] === 'find') ?? []
  expect(find.slice(1, find.indexOf('-maxdepth'))).toEqual(['./src/new.ts', './src/b.ts', './-dash.ts'])
  expect(argv.find(args => args[0] === ',behavior-map')).toEqual([',behavior-map', 'affected', 'src/new.ts'])
})

test('runs nothing for a read-only or a subagent Bash command', async ($, on) => {
  const argv = bash(on, ' M src/a.ts\0', './src/a.ts\n', 'unmapped: src\n')
  for (const command of ['git status --short', 'rg -n foo src 2>/dev/null', 'cat a.ts >&2', 'git pull --rebase']) {
    expect((await $.tool.call({ tool: 'Bash', command })).context ?? []).toEqual([])
  }
  expect((await $.tool.call({ tool: 'Bash', command: 'echo x > src/a.ts', agentId: 'a1' } as never)).context ?? []).toEqual([])
  expect(argv).toEqual([])
})

test('checks bundled and long in-place flags', async ($, on) => {
  const argv = bash(on, '', '', '')
  for (const command of ['perl -0pi -e s/a/b/ src/a.ts', 'sed --in-place s/a/b/ src/a.ts', 'sed -i.bak s/a/b/ src/a.ts']) await $.tool.call({ tool: 'Bash', command })
  expect(argv.filter(args => args[0] === 'sh')).toHaveLength(3)
})

test('does not ask for an area when a Bash command changes only docs or tests there', async ($, on) => {
  bash(on, ' M docs/a.md\0?? src/a.test.ts\0', './docs/a.md\n./src/a.test.ts\n', 'unmapped: docs, src\n2 files; 2 outside every mapped area\n')
  expect((await $.tool.call({ tool: 'Bash', command: 'echo x > docs/a.md' })).context ?? []).toEqual([])
})

test('names the entries a Bash command touched', async ($, on) => {
  bash(on, ' M src/a.ts\0', './src/a.ts\n', 'entry auth/login: src/a.ts\n1 files; 0 outside every mapped area\n')
  expect((await $.tool.call({ tool: 'Bash', command: 'perl -pi -e s/a/b/ src/a.ts' })).context?.join('\n')).toMatch(/touches auth\/login\./)
})

test('adds nothing when a writing Bash command changed no file', async ($, on) => {
  const argv = bash(on, ' M src/a.ts\0', '', 'entry auth/login: src/a.ts\n')
  expect((await $.tool.call({ tool: 'Bash', command: 'touch /tmp/x' })).context ?? []).toEqual([])
  expect(argv.some(args => args[0] === ',behavior-map')).toBe(false)
})

test('adds nothing for a Bash change in a scratch repo', async ($, on) => {
  const argv = bash(on, ' M src/a.ts\0', './src/a.ts\n', 'unmapped: src\n', '/private/tmp/clone\n')
  expect((await $.tool.call({ tool: 'Bash', command: 'echo x > src/a.ts' })).context ?? []).toEqual([])
  expect(argv.some(args => args[0] === ',behavior-map')).toBe(false)
})
