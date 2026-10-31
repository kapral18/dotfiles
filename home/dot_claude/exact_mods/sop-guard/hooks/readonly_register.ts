import type { EngineInterface, Register } from 'claude-code'

import { base, simpleCommands, type Simple } from './shell'

// A pipeline that ends in one of these still prints.
const PRINTS = new Set(['cat', 'head', 'tail', 'less', 'more', 'grep', 'rg', 'sed', 'awk', 'jq', 'tee', 'xxd', 'od', 'base64', 'strings', 'cut', 'tr', 'sort', 'uniq', 'column'])
// `pass` subcommands that print no secret.
const PASS_COMMANDS = new Set(['ls', 'list', 'find', 'search', 'grep', 'insert', 'add', 'edit', 'generate', 'rm', 'remove', 'delete', 'mv', 'rename', 'cp', 'copy', 'git', 'init', 'help', 'version'])
const ENV_FILE = /^\.env(\.(?!(example|sample|template|dist)$)[\w-]+)*$/

const TMUX_FLAG_ARGS = new Set(['-f', '-c', '-T'])
const TMUX_MUTATIONS = new Set([
  'new-session', 'new', 'kill-session', 'source-file', 'source', 'set-option', 'set', 'run-shell', 'run',
  'display-popup', 'popup', 'switch-client', 'switchc', 'attach-session', 'attach', 'a', 'at',
  'detach-client', 'detach', 'send-keys', 'send',
])

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

// Commands that print their arguments; a secret substituted into one still reaches the transcript.
const ECHOES = new Set([...PRINTS, 'echo', 'printf', 'print'])
const SHELLS = new Set(['sh', 'bash', 'zsh', 'dash', 'fish', 'ksh'])

// Commands that take a secret as an argument without printing it.
const CONSUMERS = new Set(['curl', 'wget', 'gh', 'op', 'pass', 'security', 'pbcopy', 'xclip', 'wl-copy', 'xh', 'http', 'docker', 'podman', 'helm', 'kubectl', 'npm', 'gpg', 'ssh-add', 'git', 'wc', 'shasum', 'sha256sum', 'md5'])

// A pipe consumes a secret only when it ends in a known consumer; anything else (an interpreter,
// `rev`, `ls` echoing a bad path into stderr) counts as printing. xargs also needs no printer or shell.
const printsInput = (words: string[]) => {
  const [word, ...args] = words
  if (base(word) !== 'xargs') return !CONSUMERS.has(base(word))
  return !args.some(arg => CONSUMERS.has(base(arg))) || args.some(arg => ECHOES.has(base(arg)) || SHELLS.has(base(arg)))
}

const isConsumed = (command: Simple, outer: Simple | undefined) => {
  if (command.isRedirected) return true
  const last = command.after[command.after.length - 1]
  if (last !== undefined && (last.isRedirected || !printsInput(last.words))) return true
  return command.isSubstituted && !(outer && ECHOES.has(base(outer.words[0])))
}

// The bodies of `$(...)` and backticks inside one word, outermost first.
const substitutions = (word: string) => {
  const bodies: string[] = []
  for (let i = 0; i < word.length; i++) {
    if (word.startsWith('$(', i)) {
      let depth = 0
      for (let j = i + 1; j < word.length; j++) {
        if (word[j] === '(') depth++
        else if (word[j] === ')' && --depth === 0) {
          bodies.push(word.slice(i + 2, j))
          i = j
          break
        }
      }
    } else if (word[i] === '`') {
      const end = word.indexOf('`', i + 1)
      if (end > i) {
        bodies.push(word.slice(i + 1, end))
        i = end
      }
    }
  }
  return bodies
}

// Whether `script` prints a secret into the transcript, looking into quoted substitutions and `sh -c` strings.
const leaksSecret = (script: string, depth = 0): boolean => {
  if (depth > 3) return false
  const commands = simpleCommands(script)
  return commands.some((command, i) => {
    const outer = command.isSubstituted ? commands.slice(0, i).reverse().find(c => !c.isSubstituted) : undefined
    if (printsSecret(command.words) && !isConsumed(command, outer)) return true
    const [word, ...args] = command.words
    if (SHELLS.has(base(word))) {
      const at = args.findIndex(arg => /^-[a-z]*c[a-z]*$/.test(arg))
      if (at >= 0 && args[at + 1] !== undefined && leaksSecret(args[at + 1] ?? '', depth + 1)) return true
    }
    return (
      ECHOES.has(base(word)) &&
      !isConsumed(command, undefined) &&
      args.some(arg => substitutions(arg).some(body => simpleCommands(body).some(inner => printsSecret(inner.words) && !isConsumed(inner, undefined))))
    )
  })
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

export const register: Register = on => {
  // Stops that a retry may pass, per session.
  const stopped = new Set<string>()
  const stopOnce = (key: string) => (stopped.has(key) ? false : (stopped.add(key), true))

  on('session.end', ($, e, next) => {
    stopped.clear()
    return next(e)
  })

  on('tool.call', { tool: 'Bash' }, async ($, e, next) => {
    const name = $.plugin.name
    if (leaksSecret(e.command)) {
      return { deny: `${name}: this command prints a secret into the transcript (~/AGENTS.md §5). Pass it by reference: $(...) into a variable or a consuming command's argument, a pipe into its consumer, or pass -c.` }
    }
    for (const command of simpleCommands(e.command)) {
      const [word, ...args] = command.words
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
    return next(e)
  }).catch(($, e, next) => next(e))
}
