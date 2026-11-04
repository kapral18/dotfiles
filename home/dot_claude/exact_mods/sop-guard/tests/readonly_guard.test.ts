import type { On } from 'claude-code'
import { expect, test } from 'claude-code/testing'

const ran = (stdout: string, exitCode = 0) => ({ exitCode, stdout, stderr: '', isStdoutTruncated: false, isStderrTruncated: false })
const bash = (command: string) => ({ tool: 'Bash', command, description: 'test' }) as const
const edit = (file_path: string) => ({ tool: 'Edit', file_path, old_string: 'a', new_string: 'b' }) as const

type World = { managed?: string[]; links?: Record<string, string> }

const engine = (on: On, world: World = {}) => {
  const argv: string[][] = []
  on('session.id', () => ({ value: 's1' }))
  on('env.get', () => ({ value: '/home/u' }))
  on('clock.now', () => ({ value: 0 }))
  on('fs.stat', ($, e) => ({ value: { kind: 'file', size: 1, mtimeMs: 0, isLink: false, realPath: world.links?.[e.path] ?? e.path } }))
  on('process.run', ($, e) => {
    argv.push([...e.argv])
    const command = e.argv.join(' ')
    if (command.includes('chezmoi source-path') && command.startsWith('sh')) return { value: ran('/home/u/dots\n') }
    if (command.startsWith('chezmoi managed')) return { value: ran((world.managed ?? []).join('\n')) }
    if (command.startsWith('chezmoi source-path')) return { value: ran(`/home/u/dots/home/src-of${e.argv[2]}\n`) }
    return { value: ran('', 127) }
  })
  on('tool.call', () => ({ result: {} as never }))
  return argv
}

const denied = async (call: Promise<{ deny?: string }>) => (await call).deny

test('passes unsupported shell syntax without inspecting nested commands', async ($, on) => {
  engine(on)
  for (const command of [
    'pass show work/token | head -1',
    'echo "$(gh auth token)"',
    'env pass show work/token',
    'true; tmux kill-server',
    "bash -c 'pass show work/token'",
    'cat <<EOF\n$(pass show work/token)\nEOF',
  ]) {
    expect(await denied($.tool.call(bash(command))), command).toBeUndefined()
  }
})

test('records only fixed provider IDs for Bash refusals', async ($, on) => {
  const argv = engine(on)
  expect(await denied($.tool.call(bash('pass show private/fixture-token')))).toBeDefined()
  expect(await denied($.tool.call(bash('tmux kill-server private-fixture')))).toBeDefined()
  expect(await denied($.tool.call(bash('tmux send-keys private-fixture')))).toBeDefined()
  expect(argv.filter(args => args[0] === ',task')).toEqual([
    [',task', 'guard', 'log', 'sop-guard:secret', '--harness', 'claude', '--session', 's1', '--detail', 'pass'],
    [',task', 'guard', 'log', 'sop-guard:tmux-kill-server', '--harness', 'claude', '--session', 's1', '--detail', 'tmux'],
    [',task', 'guard', 'log', 'sop-guard:tmux-default-server', '--harness', 'claude', '--session', 's1', '--detail', 'tmux'],
  ])
})

test('keeps refusals when the guard ledger is missing', async ($, on) => {
  engine(on)
  expect(await denied($.tool.call(bash('pass show work/token')))).toMatch(/common secret-output command/)
})

test('refuses common direct pass output forms including grep and generate', async ($, on) => {
  engine(on)
  for (const command of [
    'pass work/token',
    'pass show work/token',
    'pass show -',
    'pass ls work/token',
    'pass list work/token',
    'pass grep token',
    'pass grep -etoken',
    'pass grep --regexp=token',
    'pass grep -f /tmp/patterns',
    'pass generate work/token 32',
    'pass generate --qrcode work/token',
    'pass generate -nq work/token',
    'pass otp --qrcode work/token',
  ]) {
    expect(await denied($.tool.call(bash(command))), command).toMatch(/common secret-output command/)
  }
})

test('passes explicit leading clipboard modes and non-output pass commands', async ($, on) => {
  engine(on)
  for (const command of [
    'pass -c work/token',
    'pass show --clip=2 work/token',
    'pass generate -nc work/token 32',
    'pass otp -c work/token',
    'pass find token',
    'pass insert work/token',
    'pass show',
    'pass grep --help',
    'pass generate',
  ]) {
    expect(await denied($.tool.call(bash(command))), command).toBeUndefined()
  }
})

test('refuses common direct provider and environment-file output forms', async ($, on) => {
  engine(on)
  for (const command of [
    'security find-generic-password -s svc -w',
    'security find-internet-password -a account -s svc -g',
    'security dump-keychain -d /tmp/keychain',
    'op read op://vault/item/field',
    'op --account work item get fixture --fields label=password',
    'op item get fixture --reveal',
    'op item get fixture --otp',
    'op signin --raw',
    'op inject --in-file /tmp/template',
    'gh auth token --hostname github.example',
    '/bin/cat ".env"',
    "cat 'app/.env.local'",
  ]) {
    expect(await denied($.tool.call(bash(command))), command).toMatch(/common secret-output command/)
  }
})

test('passes unknown provider flags and modes without inferring their behavior', async ($, on) => {
  engine(on)
  for (const command of [
    'pass show --unknown work/token',
    'pass grep --reg=token',
    'security find-generic-password -x -w',
    'op read --unknown op://vault/item/field',
    'op item get fixture',
    'op inject --in-file /tmp/template --out-file /tmp/output',
    'gh --repo fixture/project auth token',
    'cat -n .env',
  ]) {
    expect(await denied($.tool.call(bash(command))), command).toBeUndefined()
  }
})

test('keeps quoted command text as data and excludes environment-file templates', async ($, on) => {
  engine(on)
  for (const command of [
    'rg "pass show work/token|gh auth token" docs',
    "echo '$(pass show work/token)'",
    String.raw`printf %s \$\(pass\ show\ work/token\)`,
    'cat .env.example',
    'cat .envrc',
    'tmux display-message "tmux kill-server"',
  ]) {
    expect(await denied($.tool.call(bash(command))), command).toBeUndefined()
  }
})

test('keeps secret-by-reference workflows available', async ($, on) => {
  engine(on)
  for (const command of [
    'TOKEN=$(pass show work/token) ./run',
    'curl -H "Authorization: $(gh auth token)" https://api.github.com',
    'pass show work/token | pbcopy',
    'pass grep token | gh secret set TOKEN',
    'pass generate work/token > /tmp/token',
  ]) {
    expect(await denied($.tool.call(bash(command))), command).toBeUndefined()
  }
})

test('refuses direct default-server kill-server every time and passes literal isolation', async ($, on) => {
  engine(on)
  expect(await denied($.tool.call(bash('tmux kill-server')))).toMatch(/never run bare tmux kill-server/)
  expect(await denied($.tool.call(bash('tmux kill-server')))).toMatch(/kill-server/)
  expect(await denied($.tool.call(bash('tmux -L probe kill-server')))).toBeUndefined()
  expect(await denied($.tool.call(bash('tmux -S /tmp/probe.sock kill-server')))).toBeUndefined()
  expect(await denied($.tool.call(bash('tmux -L probe run-shell "tmux kill-server"')))).toBeUndefined()
})

test('reminds once per default-server mutation and resets at session end', async ($, on) => {
  engine(on)
  on('session.end', () => ({ sessionId: 's1' }))
  expect(await denied($.tool.call(bash('tmux send-keys -t 1 ls Enter')))).toMatch(/send-keys without -S or -L/)
  expect(await denied($.tool.call(bash('tmux send-keys -t 1 ls Enter')))).toBeUndefined()
  expect(await denied($.tool.call(bash('tmux -f /tmp/tmux.conf source-file fixture')))).toMatch(/source-file/)
  expect(await denied($.tool.call(bash('tmux list-panes -a')))).toBeUndefined()
  await $.session.end({ reason: 'clear', sessionId: 's1', resume: { id: 's1' } })
  expect(await denied($.tool.call(bash('tmux send-keys -t 1 ls Enter')))).toMatch(/send-keys without -S or -L/)
})

test('refuses structured writes to chezmoi targets and names their source', async ($, on) => {
  engine(on, {
    managed: ['/home/u/.zshrc', '/home/u/AGENTS.md'],
    links: {
      '/home/u/.claude/CLAUDE.md': '/home/u/AGENTS.md',
      '/home/u/dots/managed-link': '/home/u/.zshrc',
      '/tmp/managed-link': '/home/u/.zshrc',
      '/home/u/source-link': '/home/u/dots/home/dot_zshrc',
    },
  })
  expect(await denied($.tool.call(edit('/home/u/.zshrc')))).toMatch(/\/home\/u\/\.zshrc is managed by chezmoi.*src-of\/home\/u\/\.zshrc/)
  expect(await denied($.tool.call({ tool: 'Write', file_path: '/home/u/.zshrc', content: 'fixture' }))).toMatch(/is managed by chezmoi/)
  expect(await denied($.tool.call({ tool: 'NotebookEdit', notebook_path: '/home/u/.zshrc', new_source: 'fixture', cell_type: 'code' }))).toMatch(/is managed by chezmoi/)
  expect(await denied($.tool.call(edit('/home/u/.claude/CLAUDE.md')))).toMatch(/\/home\/u\/AGENTS\.md is managed/)
  expect(await denied($.tool.call(edit('/home/u/dots/managed-link')))).toMatch(/\/home\/u\/\.zshrc is managed/)
  expect(await denied($.tool.call(edit('/tmp/managed-link')))).toMatch(/\/home\/u\/\.zshrc is managed/)
  expect(await denied($.tool.call(edit('/home/u/source-link')))).toBeUndefined()
  expect(await denied($.tool.call(edit('/home/u/notes.txt')))).toBeUndefined()
  expect(await denied($.tool.call(edit('/home/u/dots/home/dot_zshrc')))).toBeUndefined()
  expect(await denied($.tool.call(edit('relative.txt')))).toBeUndefined()
})
