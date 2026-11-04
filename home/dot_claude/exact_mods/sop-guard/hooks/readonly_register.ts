import type { EngineInterface, Register } from 'claude-code'

import { base, literalInvocation } from './shell'

const PASS_COMMANDS = new Set(['find', 'search', 'insert', 'add', 'edit', 'rm', 'remove', 'delete', 'mv', 'rename', 'cp', 'copy', 'git', 'init', 'help', 'version'])
const PASS_OUTPUT_COMMANDS = new Set(['show', 'ls', 'list', 'otp', 'grep', 'generate'])
const ENV_FILE = /^\.env(\.(?!(example|sample|template|dist)$)[\w-]+)*$/
const TMUX_MUTATIONS = new Set([
  'new-session', 'new', 'kill-session', 'source-file', 'source', 'set-option', 'set', 'run-shell', 'run',
  'display-popup', 'popup', 'switch-client', 'switchc', 'attach-session', 'attach', 'a', 'at',
  'detach-client', 'detach', 'send-keys', 'send',
])

const passOutput = (args: string[]) => {
  const sub = args[0] ?? ''
  if (PASS_COMMANDS.has(sub)) return false
  let operands = PASS_OUTPUT_COMMANDS.has(sub) ? args.slice(1) : args
  if (sub === 'grep') {
    const pattern = operands[0] ?? ''
    return operands.length === 1 && (!pattern.startsWith('-') || /^(?:-[ef].+|--(?:regexp|file)=.+)$/.test(pattern))
      || operands.length === 2 && ['-e', '--regexp', '-f', '--file'].includes(operands[0] ?? '')
  }
  const flags = sub === 'generate' ? ['-n', '--no-symbols', '-q', '--qrcode', '-nq', '-qn'] : ['-q', '--qrcode']
  if (flags.includes(operands[0] ?? '')) operands = operands.slice(1)
  return operands[0] !== undefined && (operands[0] === '-' || !operands[0].startsWith('-'))
    && (operands.length === 1 || sub === 'generate' && operands.length === 2 && /^\d+$/.test(operands[1] ?? ''))
}

const securityOutput = ([sub, ...args]: string[]) => {
  if (sub === 'dump-keychain') return args[0] === '-d' && (args.length === 1 || args.length === 2 && !args[1]?.startsWith('-'))
  if (sub !== 'find-generic-password' && sub !== 'find-internet-password') return false
  let output = false
  for (let i = 0; i < args.length; i++) {
    if (['-w', '-g', '-wg', '-gw'].includes(args[i] ?? '')) output = true
    else if (['-a', '-s'].includes(args[i] ?? '') && args[i + 1] !== undefined) i++
    else return false
  }
  return output
}

const opOutput = (args: string[]) => {
  const command = ['--account', '--config'].includes(args[0] ?? '') ? args.slice(2) : args
  if (command[0] === 'read') return command.length === 2 && !command[1]?.startsWith('-')
  if (command[0] === 'signin') return command.length === 1 || command.length === 2 && command[1] === '--raw'
  if (command[0] === 'inject') return command.length === 1 || command.length === 3 && ['-i', '--in-file'].includes(command[1] ?? '')
  if (command[0] !== 'item' || command[1] !== 'get' || !command[2] || command[2].startsWith('-')) return false
  return command.length === 4 && (/^--fields=.+$/.test(command[3] ?? '') || ['--reveal', '--otp'].includes(command[3] ?? ''))
    || command.length === 5 && command[3] === '--fields'
}

const secretProvider = (name: string, args: string[]): string | undefined => {
  if (name === 'pass' && passOutput(args)) return 'pass'
  if (name === 'security' && securityOutput(args)) return 'security'
  if (name === 'op' && opOutput(args)) return 'op'
  if (name === 'gh' && args[0] === 'auth' && args[1] === 'token' && (args.length === 2 || args.length === 4 && args[2] === '--hostname')) return 'gh'
  if (name === 'cat' && args.every((arg, i) => !arg.startsWith('-') || i === 0 && arg === '--') && args.some(arg => ENV_FILE.test(base(arg)))) return 'cat'
  return undefined
}

const tmuxSubcommand = (args: string[]) => {
  let i = 0
  for (; i < args.length && args[i]?.startsWith('-'); i++) {
    const arg = args[i] ?? ''
    if (/^-[SL].+/.test(arg) || ['-S', '-L'].includes(arg) && args[i + 1] !== undefined) return undefined
    if (['-f', '-c', '-T'].includes(arg) && args[i + 1] !== undefined) i++
    else if (!['-2', '-u', '-v'].includes(arg)) return undefined
  }
  return args[i]
}

let chezmoiRoot: Promise<string | undefined> | undefined
const dotfilesRepo = ($: EngineInterface) =>
  (chezmoiRoot ??= $.process
    .run(['sh', '-c', 'git -C "$(chezmoi source-path)" rev-parse --show-toplevel'])
    .then(run => (run.exitCode === 0 ? run.stdout.trim() : undefined)))

let managed: { at: number; targets: Promise<Set<string>> } | undefined
const managedTargets = async ($: EngineInterface) => {
  const now = await $.clock.now()
  if (!managed || now - managed.at > 60_000) {
    const targets = $.process
      .run(['chezmoi', 'managed', '--path-style', 'absolute', '--include', 'files,symlinks'], { timeoutMs: 15000 })
      .then(run => new Set(run.exitCode === 0 ? run.stdout.split('\n').filter(Boolean) : []))
    managed = { at: now, targets }
  }
  return managed.targets
}

const logFire = async ($: EngineInterface, guard: string, detail: string) => {
  try {
    const session = await $.session.id()
    await $.process.run([',task', 'guard', 'log', guard, '--harness', 'claude', '--session', session, '--detail', detail.slice(0, 200)], { timeoutMs: 5000 })
  } catch { /* The ledger is best-effort. */ }
}

export const register: Register = on => {
  const stopped = new Set<string>()
  const stopOnce = (key: string) => (stopped.has(key) ? false : (stopped.add(key), true))

  on('session.end', ($, e, next) => {
    stopped.clear()
    return next(e)
  })

  on('tool.call', { tool: 'Bash' }, async ($, e, next) => {
    const name = $.plugin.name
    const words = literalInvocation(e.command)
    if (!words) return next(e)
    const [word, ...args] = words
    const provider = secretProvider(base(word), args)
    if (provider) {
      await logFire($, 'sop-guard:secret', provider)
      return { deny: `${name}: this matches a common secret-output command (~/AGENTS.md §5); use a secret reference, a consuming command, or pass -c. This is an accident-prevention check, not a security guarantee.` }
    }
    const sub = base(word) === 'tmux' ? tmuxSubcommand(args) : undefined
    if (sub === 'kill-server') {
      await logFire($, 'sop-guard:tmux-kill-server', 'tmux')
      return { deny: `${name}: never run bare tmux kill-server (k-tmux). Use an isolated -S or -L server you created.` }
    }
    if (sub && TMUX_MUTATIONS.has(sub) && stopOnce(`tmux\0${sub}`)) {
      await logFire($, 'sop-guard:tmux-default-server', 'tmux')
      return { deny: `${name}: tmux ${sub} without -S or -L changes the default server (k-tmux). Use an isolated server. Retry only if the user asked to change the current tmux environment and you verified the target.` }
    }
    return next(e)
  }).catch(($, e, next) => next(e))

  on('tool.call', { tool: ['Edit', 'Write', 'NotebookEdit'] }, async ($, e, next) => {
    const path = 'notebook_path' in e ? e.notebook_path : e.file_path
    if (!path.startsWith('/')) return next(e)
    const name = $.plugin.name

    const home = await $.env.get('HOME')
    const root = await dotfilesRepo($)
    const real = (await $.fs.stat(path, { resolve: true }).catch(() => undefined))?.realPath ?? path
    if (home && real.startsWith(`${home}/`) && !(root && real.startsWith(`${root}/`))) {
      if ((await managedTargets($)).has(real)) {
        const source = await $.process.run(['chezmoi', 'source-path', real])
        await logFire($, 'sop-guard:chezmoi-target', real)
        return { deny: `${name}: ${real} is managed by chezmoi (~/AGENTS.md §6). Edit ${source.stdout.trim() || 'its source'}, then run chezmoi apply --no-tty ${real}.` }
      }
    }
    return next(e)
  }).catch(($, e, next) => next(e))
}
