import { realpathSync } from 'node:fs'
import { homedir } from 'node:os'

import { claimOnce, deny, type HookInput, type HookOutput, logFire, run } from './hook'
import { base, literalInvocations } from './shell'

const GUARD = 'sop-guard'
const PASS_COMMANDS = new Set(['find', 'search', 'insert', 'add', 'edit', 'rm', 'remove', 'delete', 'mv', 'rename', 'cp', 'copy', 'git', 'init', 'help', 'version'])
const PASS_OUTPUT_COMMANDS = new Set(['show', 'ls', 'list', 'otp', 'grep', 'generate'])
const ENV_FILE = /^\.env(\.(?!(example|sample|template|dist)$)[\w-]+)*$/
const HERDR_TEARDOWNS = new Set([
  'session stop', 'session delete', 'workspace close', 'tab close', 'pane close', 'worktree remove',
  'server reload-config', 'config reset-keys', 'plugin unlink', 'plugin uninstall', 'plugin disable',
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

// herdr removes `--session <name>` from anywhere in argv; `default` names the
// user's own session. Returns the command words and whether the call targets
// an isolated (non-default) session.
const herdrCall = (args: string[]) => {
  let session = ''
  const words: string[] = []
  for (let i = 0; i < args.length; i++) {
    const arg = args[i] ?? ''
    if (arg.startsWith('--session=')) session = arg.slice('--session='.length)
    else if (arg === '--session') session = args[++i] ?? ''
    else if (['--machine', '--remote'].includes(arg)) i++
    else words.push(arg)
  }
  return { words, isolated: session !== '' && session !== 'default' }
}

const checkCommand = (input: HookInput, [word, ...args]: string[]): HookOutput => {
  const provider = secretProvider(base(word), args)
  if (provider) {
    logFire(input, 'sop-guard:secret', provider)
    return deny(`${GUARD}: this matches a common secret-output command (~/AGENTS.md §5); use a secret reference, a consuming command, or pass -c. This is an accident-prevention check, not a security guarantee.`)
  }
  const call = base(word) === 'herdr' ? herdrCall(args) : undefined
  const sub = call && !call.isolated && call.words.length >= 2 ? `${call.words[0]} ${call.words[1]}` : undefined
  const stopsDefault = call !== undefined && ['session stop', 'session delete'].includes(`${call.words[0]} ${call.words[1]}`)
    && call.words.slice(2).includes('default')
  if (sub === 'server stop' || stopsDefault) {
    logFire(input, 'sop-guard:herdr-server-stop', 'herdr')
    return deny(`${GUARD}: never stop the default herdr session (k-herdr server stop, session stop/delete default); it ends every pane the user has. Stop only a named --session server you created.`)
  }
  if (sub && HERDR_TEARDOWNS.has(sub)) {
    if (!claimOnce(GUARD, input.session_id, `herdr\0${sub}`)) return undefined
    logFire(input, 'sop-guard:herdr-default-session', 'herdr')
    return deny(`${GUARD}: herdr ${sub} without --session tears down the user's live session state (k-herdr). Retry only for a target you created or the user named, after verifying it.`)
  }
  return undefined
}

const checkBash = (input: HookInput): HookOutput => {
  const command = input.tool_input?.command
  for (const words of (typeof command === 'string' && literalInvocations(command)) || []) {
    const out = checkCommand(input, words)
    if (out) return out
  }
  return undefined
}

const checkEdit = (input: HookInput): HookOutput => {
  const path = input.tool_input?.notebook_path ?? input.tool_input?.file_path
  if (typeof path !== 'string' || !path.startsWith('/')) return undefined
  let real = path
  try {
    real = realpathSync(path)
  } catch { /* A new file has no real path yet. */ }
  if (!real.startsWith(`${homedir()}/`)) return undefined
  const top = run(['sh', '-c', 'git -C "$(chezmoi source-path)" rev-parse --show-toplevel'])
  if (top.exitCode === 0 && real.startsWith(`${top.stdout.trim()}/`)) return undefined
  const managed = run(['chezmoi', 'managed', '--path-style', 'absolute', '--include', 'files,symlinks'])
  if (managed.exitCode !== 0 || !managed.stdout.split('\n').includes(real)) return undefined
  const source = run(['chezmoi', 'source-path', real])
  logFire(input, 'sop-guard:chezmoi-target', real)
  return deny(`${GUARD}: ${real} is managed by chezmoi (~/AGENTS.md §6). Edit ${source.stdout.trim() || 'its source'}, then run chezmoi apply --no-tty ${real}.`)
}

export const handle = (input: HookInput): HookOutput => (input.tool_name === 'Bash' ? checkBash(input) : checkEdit(input))
