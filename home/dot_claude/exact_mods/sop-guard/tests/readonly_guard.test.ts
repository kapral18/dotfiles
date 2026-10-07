import type { On } from 'claude-code'
import { expect, test } from 'claude-code/testing'

const ran = (stdout: string, exitCode = 0) => ({ exitCode, stdout, stderr: '', isStdoutTruncated: false, isStderrTruncated: false })
const bash = (command: string) => ({ tool: 'Bash', command, description: 'test' }) as const
const edit = (file_path: string) => ({ tool: 'Edit', file_path, old_string: 'a', new_string: 'b' }) as const

type World = { managed?: string[]; links?: Record<string, string>; owners?: string; codeowners?: boolean }

// The engine beneath the plugin: HOME is /home/u, the dotfiles repo is /home/u/dots.
const engine = (on: On, world: World = {}) => {
  on('env.get', () => ({ value: '/home/u' }))
  on('clock.now', () => ({ value: 0 }))
  on('fs.exists', ($, e) => ({ value: e.path.endsWith('CODEOWNERS') ? world.codeowners === true : true }))
  on('fs.stat', ($, e) => ({ value: { kind: 'file', size: 1, mtimeMs: 0, isLink: false, realPath: world.links?.[e.path] ?? e.path } }))
  on('process.run', ($, e) => {
    const argv = e.argv.join(' ')
    if (argv.includes('chezmoi source-path') && argv.startsWith('sh')) return { value: ran('/home/u/dots\n') }
    if (argv.startsWith('chezmoi managed')) return { value: ran((world.managed ?? []).join('\n')) }
    if (argv.startsWith('chezmoi source-path')) return { value: ran(`/home/u/dots/home/src-of${e.argv[2]}\n`) }
    if (argv === 'git rev-parse --show-toplevel') {
      const repo = e.init?.cwd?.startsWith('/work/kibana') ? '/work/kibana' : undefined
      return { value: repo ? ran(`${repo}\n`) : ran('', 128) }
    }
    if (argv.startsWith(',codeowners')) return { value: ran(`${e.argv[2]}  pattern  ${world.owners ?? '<unowned>'}\n`, world.owners ? 0 : 2) }
    return { value: ran('', 127) }
  })
  on('tool.call', () => ({ result: {} as never }))
}

const denied = async (call: Promise<{ deny?: string }>) => (await call).deny

test('refuses commands that print a secret', async ($, on) => {
  engine(on)
  for (const command of [
    'pass show work/token',
    'pass work/token',
    'pass show work/token | head -1',
    'security find-generic-password -s svc -w',
    'op read op://vault/item/field',
    'gh auth token',
    'cat .env',
    'cd app && cat config/.env | grep KEY',
    'pass show work/token >&2',
    'pass show work/token 2>/dev/null',
  ]) {
    expect(await denied($.tool.call(bash(command)))).toMatch(/prints a secret/)
  }
})

test('lets a secret pass by reference', async ($, on) => {
  engine(on)
  for (const command of [
    'TOKEN=$(pass show work/token) ./run',
    'curl -H "Authorization: $(gh auth token)" https://api.github.com',
    'pass show work/token | pbcopy',
    'pass show ${ENTRY} | pbcopy',
    'pass -c work/token',
    'pass ls',
    'pass show work/token > /tmp/x/token',
    'gh auth token >/dev/null 2>&1 || gh auth login',
    'rg "pass show" docs',
    'cat .envrc',
  ]) {
    expect(await denied($.tool.call(bash(command))), command).toBeUndefined()
  }
})

test('refuses bare tmux kill-server every time', async ($, on) => {
  engine(on)
  expect(await denied($.tool.call(bash('tmux kill-server')))).toMatch(/never run bare tmux kill-server/)
  expect(await denied($.tool.call(bash('tmux kill-server')))).toMatch(/kill-server/)
  expect(await denied($.tool.call(bash('tmux -L probe kill-server')))).toBeUndefined()
  expect(await denied($.tool.call(bash('tmux -S "$sock" kill-server')))).toBeUndefined()
})

test('stops a default-server mutation once and lets reads through', async ($, on) => {
  engine(on)
  expect(await denied($.tool.call(bash('tmux send-keys -t 1 ls Enter')))).toMatch(/send-keys without -S or -L/)
  expect(await denied($.tool.call(bash('tmux send-keys -t 1 ls Enter')))).toBeUndefined()
  expect(await denied($.tool.call(bash('tmux -f ~/.tmux.conf source-file x')))).toMatch(/source-file/)
  expect(await denied($.tool.call(bash('tmux list-panes -a && tmux capture-pane -p -t 1')))).toBeUndefined()
  expect(await denied($.tool.call(bash('rg "tmux kill-server" docs')))).toBeUndefined()
})

test('refuses direct Buildkite fetches', async ($, on) => {
  engine(on)
  expect(await denied($.tool.call({ tool: 'WebFetch', url: 'https://buildkite.com/elastic/kibana/builds/1', prompt: 'x' }))).toMatch(/use bk/)
  expect(await denied($.tool.call(bash('curl -s https://api.buildkite.com/v2/builds')))).toMatch(/use bk/)
  expect(await denied($.tool.call({ tool: 'WebFetch', url: 'https://notbuildkite.com.example.org/', prompt: 'x' }))).toBeUndefined()
  expect(await denied($.tool.call(bash('bk build view 1')))).toBeUndefined()
})

test('refuses edits to chezmoi targets and names the source', async ($, on) => {
  engine(on, { managed: ['/home/u/.zshrc', '/home/u/AGENTS.md'], links: { '/home/u/.claude/CLAUDE.md': '/home/u/AGENTS.md' } })
  expect(await denied($.tool.call(edit('/home/u/.zshrc')))).toMatch(/\/home\/u\/\.zshrc is managed by chezmoi.*src-of\/home\/u\/\.zshrc/)
  expect(await denied($.tool.call(edit('/home/u/.claude/CLAUDE.md')))).toMatch(/\/home\/u\/AGENTS\.md is managed/)
  expect(await denied($.tool.call(edit('/home/u/notes.txt')))).toBeUndefined()
  expect(await denied($.tool.call(edit('/home/u/dots/home/dot_zshrc')))).toBeUndefined()
})

test('stops an edit outside the team once per owner set', async ($, on) => {
  engine(on, { codeowners: true, owners: '@elastic/kibana-core' })
  expect(await denied($.tool.call(edit('/work/kibana/src/core/a.ts')))).toMatch(/owned by @elastic\/kibana-core, not @elastic\/kibana-management/)
  expect(await denied($.tool.call(edit('/work/kibana/src/core/b.ts')))).toBeUndefined()
})

test('lets team-owned edits through', async ($, on) => {
  engine(on, { codeowners: true, owners: '@elastic/kibana-security @elastic/kibana-management' })
  expect(await denied($.tool.call(edit('/work/kibana/src/console/a.ts')))).toBeUndefined()
})

test('passes repos without CODEOWNERS', async ($, on) => {
  engine(on, { codeowners: false, owners: '@elastic/kibana-core' })
  expect(await denied($.tool.call(edit('/work/kibana/src/core/a.ts')))).toBeUndefined()
})

test('asks for the team once when none is set', { options: { team: '' } }, async ($, on) => {
  engine(on, { codeowners: true, owners: '@elastic/kibana-core' })
  expect(await denied($.tool.call(edit('/work/kibana/src/core/a.ts')))).toMatch(/Ask the user for their team/)
  expect(await denied($.tool.call(edit('/work/kibana/src/core/a.ts')))).toBeUndefined()
})

test('sees commands behind assignments, wrappers, keywords, and braces', async ($, on) => {
  engine(on)
  for (const command of [
    'GH_HOST=x gh auth token',
    'env pass show x',
    'if true; then gh auth token; fi',
    '{ gh auth token; }',
    'pass show "work/token"',
    'cat ".env"',
    'cat ${DIR}/.env',
    "pass show x | grep -E 'a|b'",
    "pass show x | jq -r '.a | .b'",
  ]) {
    expect(await denied($.tool.call(bash(command))), command).toMatch(/prints a secret/)
  }
  expect(await denied($.tool.call(bash('TMUX= tmux kill-server'))), 'tmux env').toMatch(/kill-server/)
  expect(await denied($.tool.call(bash('TERM=xterm curl "https://buildkite.com/x"'))), 'bk env').toMatch(/use bk/)
  expect(await denied($.tool.call(bash(String.raw`tmux display -p x \; display-popup -E ls`)))).toMatch(/display-popup/)
})

test('ignores quoted text and heredoc bodies', async ($, on) => {
  engine(on)
  for (const command of [
    "rg -n 'TOKEN|gh auth token' docs",
    'rg "foo|pass show" home',
    "git commit -F - <<'EOF'\nfix: pass the token through env\nop read is not used\nEOF",
    "git commit -m \"$(cat <<'EOF'\npass the token\nEOF\n)\"",
    'pass show -c work/token',
    'pass show',
    'cat .env.example',
  ]) {
    expect(await denied($.tool.call(bash(command))), command).toBeUndefined()
  }
})
