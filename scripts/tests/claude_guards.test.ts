import { afterAll, describe, expect, test } from 'bun:test'
import { chmodSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, realpathSync, rmSync, symlinkSync, writeFileSync } from 'node:fs'
import { join, resolve } from 'node:path'

import { literalInvocations } from '../../home/dot_claude/exact_guards/shell'

const root = realpathSync(mkdtempSync('/tmp/claude-guards-test-'))
const home = join(root, 'home')
const state = join(root, 'tmp')
const guardState = join(state, 'claude-guards')
mkdirSync(join(home, 'bin'), { recursive: true })
// ,task and the behavior map, as the guards call them from ~/bin: ,task records each call, `affected` prints $HOME/affected.
writeFileSync(join(home, 'bin', ',task'), '#!/bin/sh\necho "$*" >>"$HOME/task-calls"\nexit 0\n')
writeFileSync(join(home, 'bin', ',behavior-map'), '#!/bin/sh\n[ -f "$HOME/affected" ] && cat "$HOME/affected"\nexit 0\n')
// chezmoi on PATH: `managed` lists $HOME/.zshrc; `source-path <target>` names its source.
writeFileSync(join(home, 'bin', 'chezmoi'), '#!/bin/sh\ncase "$1" in managed) echo "$HOME/.zshrc" ;; source-path) [ -n "$2" ] && echo "/src/dot_zshrc" || echo /nonexistent ;; esac\n')
for (const tool of [',task', ',behavior-map', 'chezmoi']) chmodSync(join(home, 'bin', tool), 0o755)
afterAll(() => rmSync(root, { recursive: true, force: true }))

const GUARDS = resolve(import.meta.dir, '../../home/dot_claude/exact_guards')
const SCRIPTS = {
  guards: join(GUARDS, 'guards.ts'),
  dotfiles: resolve(import.meta.dir, '../../.claude/hooks/dotfiles-guard.ts'),
}

type Out = { hookSpecificOutput?: { permissionDecision?: string; permissionDecisionReason?: string; additionalContext?: string } }

// One command-hook run, as Claude Code makes it: the payload on stdin, the answer on stdout.
const hook = (script: string, payload: object): Out => {
  const done = Bun.spawnSync([process.execPath, script], { stdin: Buffer.from(JSON.stringify(payload)), env: { ...process.env, HOME: home, TMPDIR: state, PATH: `${join(home, 'bin')}:${process.env.PATH}` } })
  return JSON.parse(done.stdout.toString()) as Out
}
const bash = (command: string, extra: Record<string, unknown> = {}) => ({
  session_id: 's1', cwd: root, hook_event_name: 'PreToolUse', tool_name: 'Bash', tool_input: { command }, tool_use_id: 'c1', ...extra,
})
const denial = (out: Out) => out.hookSpecificOutput?.permissionDecisionReason

test('shell commands split into literal command lists; other syntax stays opaque', () => {
  expect(literalInvocations("cd 'app' && git push")).toEqual([['cd', 'app'], ['git', 'push']])
  expect(literalInvocations('a; b || c\nd')).toEqual([['a'], ['b'], ['c'], ['d']])
  expect(literalInvocations("printf '%s' 'a && b; c'")).toEqual([['printf', '%s', 'a && b; c']])
  for (const opaque of ['pass show x | head -1', 'echo "$(gh auth token)"', 'sleep 1 &', 'X=1 make test', "bash -c 'x' > out"]) {
    expect(literalInvocations(opaque), opaque).toBeUndefined()
  }
})

test('a refusal ends the guard chain before ,task records the call', () => {
  rmSync(join(home, 'task-calls'), { force: true })
  expect(denial(hook(SCRIPTS.guards, bash('pass show work/token')))).toMatch(/common secret-output command/)
  expect(readFileSync(join(home, 'task-calls'), 'utf8')).not.toContain('hook claude')
  expect(hook(SCRIPTS.guards, bash('git status'))).toEqual({})
  expect(readFileSync(join(home, 'task-calls'), 'utf8')).toContain('hook claude')
})

test('logs each call that ran, for stop-review, until the session ends', () => {
  const log = join(guardState, 'stop-review.s5.calls')
  const edit = { session_id: 's5', cwd: root, tool_name: 'Edit', tool_input: { file_path: '/elsewhere/a.ts' }, tool_use_id: 'e5', agent_id: 'w1' }
  for (const event of ['PreToolUse', 'PostToolUseFailure', 'PostToolUse']) hook(SCRIPTS.guards, { ...edit, hook_event_name: event })
  hook(SCRIPTS.guards, { ...bash('false', { session_id: 's5', agent_id: 'w1' }), hook_event_name: 'PostToolUseFailure' })
  expect(readFileSync(log, 'utf8')).toBe('{"tool":"Edit","path":"/elsewhere/a.ts","agent":"w1"}\n{"tool":"Bash","agent":"w1"}\n')
  hook(SCRIPTS.guards, { session_id: 's5', cwd: root, hook_event_name: 'SessionEnd' })
  expect(readdirSync(guardState)).not.toContain('stop-review.s5.calls')
})

describe('sop-guard', () => {
  test('refuses an edit of a chezmoi-managed target, also through a symlink, and names its source', () => {
    writeFileSync(join(home, '.zshrc'), '')
    symlinkSync(join(home, '.zshrc'), join(home, 'zshrc-link'))
    const edit = (file_path: string) => ({ session_id: 's1', cwd: root, hook_event_name: 'PreToolUse', tool_name: 'Edit', tool_input: { file_path }, tool_use_id: 'e1' })
    for (const path of ['.zshrc', 'zshrc-link']) expect(denial(hook(SCRIPTS.guards, edit(join(home, path)))), path).toMatch(/managed by chezmoi.*\/src\/dot_zshrc/)
    for (const path of ['other', 'new/file.ts']) expect(denial(hook(SCRIPTS.guards, edit(join(home, path)))), path).toBeUndefined()
  })

  test('refuses a secret-output command, also after a Code Mode cd prefix', () => {
    for (const command of ['pass show work/token', "cd '/repo' && gh auth token", 'true; op read op://v/i/f', 'cat .env.local']) {
      expect(denial(hook(SCRIPTS.guards, bash(command))), command).toMatch(/common secret-output command/)
    }
    for (const command of ['pass show work/token | pbcopy', 'pass -c work/token', 'cat .env.example', 'git push']) {
      expect(denial(hook(SCRIPTS.guards, bash(command))), command).toBeUndefined()
    }
  })

  test('stops a default herdr teardown once per session, until the session ends', () => {
    expect(denial(hook(SCRIPTS.guards, bash('herdr pane close w1:p2')))).toMatch(/tears down/)
    expect(denial(hook(SCRIPTS.guards, bash('herdr pane close w1:p2')))).toBeUndefined()
    expect(denial(hook(SCRIPTS.guards, bash('herdr pane close w1:p2', { session_id: 's2' })))).toMatch(/tears down/)
    expect(hook(SCRIPTS.guards, { session_id: 's1', cwd: root, hook_event_name: 'SessionEnd' })).toEqual({})
    expect(readdirSync(guardState).filter(name => name.startsWith('sop-guard.s1.'))).toEqual([])
    expect(denial(hook(SCRIPTS.guards, bash('herdr server stop')))).toMatch(/never stop the default herdr session/)
    expect(denial(hook(SCRIPTS.guards, bash('herdr --session mine server stop')))).toBeUndefined()
  })
})

test('dotfiles-guard refuses the checks reserved for the human, read as commands', () => {
  for (const command of ['make check-full', "cd '/repo' && make test", 'timeout -k 5 600 python3 scripts/test_runner.py', './bin/check --full', 'uv run scripts/check.py --full']) {
    expect(denial(hook(SCRIPTS.dotfiles, bash(command))), command).toMatch(/reserves make check-full/)
  }
  for (const command of ['make check', 'git add scripts/test_runner.py', 'rg -n "make test" docs', "python3 -c 'print(1)' scripts/test_runner.py", 'make test | tee log']) {
    expect(denial(hook(SCRIPTS.dotfiles, bash(command))), command).toBeUndefined()
  }
})

describe('behavior-map-guard', () => {
  // Git reports a non-scratch worktree containing the real temporary fixture.
  const repo = '/'
  writeFileSync(join(home, 'bin', 'git'), `#!/bin/sh
case "$1 $2" in
  'rev-parse --show-toplevel') echo / ;;
  '--no-optional-locks status') printf '?? %s/a.ts\\0' "\${HOME#/}" ;;
  *) exit 1 ;;
esac
`, { mode: 0o755 })
  const edit = (event: string, session = 's1') => ({
    session_id: session, cwd: repo, hook_event_name: event, tool_name: 'Edit', tool_input: { file_path: join(repo, 'src', 'a.ts') }, tool_use_id: 'e1',
  })

  test('refuses an edit in an unmapped directory once per session', () => {
    writeFileSync(join(home, 'affected'), 'unmapped: src\n')
    expect(denial(hook(SCRIPTS.guards, edit('PreToolUse')))).toMatch(/src in .* has no behavior-map area/)
    expect(hook(SCRIPTS.guards, edit('PreToolUse'))).toEqual({})
    expect(denial(hook(SCRIPTS.guards, edit('PreToolUse', 's3')))).toMatch(/no behavior-map area/)
  })

  test('notes the entries a shell write touched, after it ran', () => {
    writeFileSync(join(home, 'affected'), 'entry app/core: src/a.ts\n')
    const call = bash('touch src/a.ts', { cwd: repo, session_id: 's4' })
    expect(hook(SCRIPTS.guards, call)).toEqual({})
    writeFileSync(join(home, 'a.ts'), 'x')
    const after = hook(SCRIPTS.guards, { ...call, hook_event_name: 'PostToolUse' })
    expect(after.hookSpecificOutput?.additionalContext).toMatch(/this edit touches app\/core/)
  })
})
