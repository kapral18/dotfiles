import type { EngineInterface, Register } from 'claude-code'

import { base, simpleCommands, type Simple } from './shell'

// A pipeline that ends in one of these still prints.
const PRINTS = new Set(['cat', 'head', 'tail', 'less', 'more', 'grep', 'rg', 'sed', 'awk', 'jq', 'tee', 'xxd', 'od', 'base64', 'strings', 'cut', 'tr', 'sort', 'uniq', 'column'])
// `pass` subcommands that print no secret.
const PASS_COMMANDS = new Set(['ls', 'list', 'find', 'search', 'grep', 'insert', 'add', 'edit', 'generate', 'rm', 'remove', 'delete', 'mv', 'rename', 'cp', 'copy', 'git', 'init', 'help', 'version'])
const ENV_FILE = /^\.env(\.(?!(example|sample|template|dist)$)[\w-]+)*$/
const BUILDKITE = /(^|\/\/|[.@])buildkite\.com\b/

const TMUX_FLAG_ARGS = new Set(['-f', '-c', '-T'])
const TMUX_MUTATIONS = new Set([
  'new-session', 'new', 'kill-session', 'source-file', 'source', 'set-option', 'set', 'run-shell', 'run',
  'display-popup', 'popup', 'switch-client', 'switchc', 'attach-session', 'attach', 'a', 'at',
  'detach-client', 'detach', 'send-keys', 'send',
])

const parent = (path: string) => path.slice(0, Math.max(path.lastIndexOf('/'), 0)) || '/'

const printsSecret = ([name, ...args]: string[]) => {
  switch (base(name)) {
    case 'pass': {
      if (args.some(arg => /^(-c\d*|--clip|-q|--qrcode)(=|$)/.test(arg))) return false
      const sub = args[0] ?? ''
      const entries = sub === 'show' || sub === 'otp' ? args.slice(1) : PASS_COMMANDS.has(sub) ? [] : args
      return entries.some(arg => !arg.startsWith('-'))
    }
    case 'security':
      return /^find-(generic|internet)-password$/.test(args[0] ?? '') && (args.includes('-w') || args.includes('-g'))
    case 'op':
      return args[0] === 'read' || (args[0] === 'item' && args.includes('--reveal'))
    case 'gh':
      return args[0] === 'auth' && args[1] === 'token'
    case 'cat':
      return args.some(arg => ENV_FILE.test(base(arg)))
    default:
      return false
  }
}

const isConsumed = (command: Simple) => {
  if (command.isSubstituted || command.isRedirected) return true
  const last = command.after[command.after.length - 1]
  return last !== undefined && (last.isRedirected || !PRINTS.has(base(last.words[0])))
}

// Global flags, then the first subcommand and each one after `\;`.
const tmuxSubcommands = (args: string[]) => {
  let i = 0
  for (; i < args.length; i++) {
    const arg = args[i] ?? ''
    if (/^-[SL]/.test(arg)) return undefined
    if (TMUX_FLAG_ARGS.has(arg)) i++
    else if (!arg.startsWith('-')) break
  }
  const subs = args[i] ? [args[i] ?? ''] : []
  args.forEach((arg, j) => (arg === '\\;' || arg === ';') && args[j + 1] && subs.push(args[j + 1] ?? ''))
  return subs
}

// Cached per process: the dotfiles repo root, and chezmoi's managed targets for a minute.
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

export const register: Register = (on, options) => {
  const team = typeof options.team === 'string' ? options.team.trim() : ''
  // Stops that a retry may pass, per session.
  const stopped = new Set<string>()
  const stopOnce = (key: string) => (stopped.has(key) ? false : (stopped.add(key), true))

  on('session.end', ($, e, next) => {
    stopped.clear()
    return next(e)
  })

  on('tool.call', { tool: 'Bash' }, async ($, e, next) => {
    const name = $.plugin.name
    const commands = simpleCommands(e.command)

    for (const command of commands) {
      const [word, ...args] = command.words
      if (printsSecret(command.words) && !isConsumed(command)) {
        return { deny: `${name}: this command prints a secret into the transcript (~/AGENTS.md §5). Pass it by reference: $(...) into a variable or argument, a pipe into its consumer, or pass -c.` }
      }
      if (/^(curl|wget|http|https|xh)$/.test(base(word)) && args.some(arg => BUILDKITE.test(arg))) {
        return { deny: `${name}: never fetch buildkite.com directly; use bk (k-buildkite skill).` }
      }
      if (base(word) !== 'tmux') continue
      for (const sub of tmuxSubcommands(args) ?? []) {
        if (sub === 'kill-server') {
          return { deny: `${name}: never run bare tmux kill-server (k-tmux). Use an isolated -S or -L server you created.` }
        }
        if (TMUX_MUTATIONS.has(sub) && stopOnce(`tmux\0${sub}`)) {
          return { deny: `${name}: tmux ${sub} without -S or -L changes the default server (k-tmux). Use an isolated server. Retry only if the user asked to change the current tmux environment and you verified the target.` }
        }
      }
    }
    return next(e)
  }).catch(($, e, next) => next(e))

  on('tool.call', { tool: 'WebFetch' }, ($, e, next) => {
    const host = /^[a-z]+:\/\/([^/?#]+)/i.exec(e.url)?.[1] ?? ''
    return BUILDKITE.test(`//${host}`) ? { deny: `${$.plugin.name}: never fetch buildkite.com directly; use bk (k-buildkite skill).` } : next(e)
  }).catch(($, e, next) => next(e))

  on('tool.call', { tool: ['Edit', 'Write', 'NotebookEdit'] }, async ($, e, next) => {
    const path = 'notebook_path' in e ? e.notebook_path : e.file_path
    if (!path.startsWith('/')) return next(e)
    const name = $.plugin.name

    const home = await $.env.get('HOME')
    const root = await dotfilesRepo($)
    if (home && path.startsWith(`${home}/`) && !(root && path.startsWith(`${root}/`))) {
      const real = (await $.fs.stat(path, { resolve: true }).catch(() => undefined))?.realPath ?? path
      if ((await managedTargets($)).has(real)) {
        const source = await $.process.run(['chezmoi', 'source-path', real])
        return { deny: `${name}: ${real} is managed by chezmoi (~/AGENTS.md §6). Edit ${source.stdout.trim() || 'its source'}, then run chezmoi apply --no-tty ${real}.` }
      }
    }

    let dir = parent(path)
    while (dir !== '/' && !(await $.fs.exists(dir))) dir = parent(dir)
    const top = await $.process.run(['git', 'rev-parse', '--show-toplevel'], { cwd: dir })
    const repo = top.stdout.trim()
    if (top.exitCode !== 0) return next(e)
    // The places ,codeowners reads.
    const files = ['.github/CODEOWNERS', 'CODEOWNERS', 'docs/CODEOWNERS'].map(file => `${repo}/${file}`)
    if (!(await Promise.all(files.map(file => $.fs.exists(file)))).includes(true)) return next(e)
    if (!team) {
      return stopOnce(`team\0${repo}`)
        ? { deny: `${name}: ${repo} has CODEOWNERS and no team is set (~/AGENTS.md §5). Ask the user for their team once, then retry.` }
        : next(e)
    }
    const relative = path.startsWith(`${repo}/`) ? path.slice(repo.length + 1) : path
    const owner = await $.process.run([',codeowners', '--owner-of', relative], { cwd: repo })
    const owners = owner.stdout.trim().split(/\s{2,}/)[2] ?? '<unowned>'
    if (owners.split(/\s+/).includes(team) || !stopOnce(`owners\0${repo}\0${owners}`)) return next(e)
    return { deny: `${name}: ${relative} is owned by ${owners}, not ${team} (~/AGENTS.md §5). Stop and list the owners for the user. Retry only after the user approves.` }
  }).catch(($, e, next) => next(e))
}
