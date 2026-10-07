import type { Register } from 'claude-code'

// A copy of sop-guard's scanner; scripts/tests/test_claude_mods.py keeps them equal.
import { base, simpleCommands } from './shell'

// make flags whose next word is their value, not a target.
const MAKE_VALUE_FLAGS = new Set(['-C', '-f', '-I', '-o', '-W', '--directory', '--file'])

const isReservedCheck = ([name, ...args]: string[]) => {
  const command = base(name)
  if (command === 'make') return args.some((arg, i) => (arg === 'test' || arg === 'check-full') && !MAKE_VALUE_FLAGS.has(args[i - 1] ?? ''))
  if ((name ?? '').endsWith('bin/check')) return args.includes('--full')
  if (/^(python3?|uv)$/.test(command) && args.some(arg => arg.endsWith('scripts/check.py'))) return args.includes('--full')
  if (command === 'test_runner.py') return true
  return /^(python3?|uv)$/.test(command) && args.some(arg => arg.endsWith('scripts/test_runner.py'))
}

export const register: Register = on => {
  on('tool.call', { tool: 'Bash' }, ($, e, next) =>
    simpleCommands(e.command).some(command => isReservedCheck(command.words))
      ? { deny: `${$.plugin.name}: AGENTS.md reserves make check-full, make test, and bin/check --full for the human, and the user reserved scripts/test_runner.py and scripts/check.py --full. Run make check.` }
      : next(e),
  ).catch(($, e, next) => next(e))
}
