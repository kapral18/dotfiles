import type { Register } from 'claude-code'

// A copy of sop-guard's scanner; scripts/tests/test_claude_mods.py keeps them equal.
import { base, literalInvocation } from './shell'

// make flags whose next word is their value, not a target.
const MAKE_VALUE_FLAGS = new Set(['-C', '-f', '-I', '-o', '-W', '--directory', '--file'])

// getopt rules: in a short group the first k or s takes the rest of the word, or the next word when nothing follows;
// a long option, or an unambiguous prefix of one, takes the next word unless it has =.
const takesValue = (word: string) => {
  if (word.startsWith('--')) {
    const name = word.slice(2)
    return name.length > 0 && !name.includes('=') && ['kill-after', 'signal'].some(option => option.startsWith(name))
  }
  const at = word.slice(1).search(/[ks]/)
  return at >= 0 && at === word.length - 2
}

// ~/AGENTS.md requires `timeout <seconds> <command>` for checks, so the guard reads the command it runs.
const unwrapTimeout = (words: string[]): string[] => {
  if (!['timeout', 'gtimeout'].includes(base(words[0]))) return words
  let i = 1
  for (; i < words.length && (words[i] ?? '').startsWith('-'); i++) {
    if (words[i] === '--') {
      i++
      break
    }
    if (takesValue(words[i] ?? '')) i++
  }
  return unwrapTimeout(words.slice(i + 1))
}

const isReservedCheck = ([name, ...args]: string[]) => {
  const command = base(name)
  if (command === 'make') {
    let reserved = false
    for (let i = 0; i < args.length; i++) {
      const arg = args[i] ?? ''
      if (MAKE_VALUE_FLAGS.has(arg)) {
        if (args[++i] === undefined) return false
      } else if (arg.startsWith('-')) return false
      else if (arg === 'test' || arg === 'check-full') reserved = true
    }
    return reserved
  }
  if ((name ?? '').endsWith('bin/check')) return args.includes('--full')
  if (command === 'test_runner.py') return true
  let scriptAt = 0
  if (/^python3?$/.test(command)) {
    if (args[0] === '-u') scriptAt = 1
  } else if (command === 'uv' && args[0] === 'run') scriptAt = 1
  else return false
  const script = args[scriptAt] ?? ''
  return script.endsWith('scripts/test_runner.py') || script.endsWith('scripts/check.py') && args.slice(scriptAt + 1).includes('--full')
}

export const register: Register = on => {
  on('tool.call', { tool: 'Bash' }, ($, e, next) => {
    const words = literalInvocation(e.command)
    return words && isReservedCheck(unwrapTimeout(words))
      ? { deny: `${$.plugin.name}: AGENTS.md reserves make check-full, make test, and bin/check --full for the human, and the user reserved scripts/test_runner.py and scripts/check.py --full. Run make check.` }
      : next(e)
  }).catch(($, e, next) => next(e))
}
