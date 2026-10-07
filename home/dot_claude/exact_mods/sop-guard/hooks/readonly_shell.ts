// A small reading of a Bash command: the simple commands it runs, by command word.
// Quoted text and heredoc bodies are data, never commands, so they are blanked first.

export type Simple = {
  // The words after assignments, wrappers, and keywords, quotes removed.
  words: string[]
  // Inside $(...) or backticks: its stdout feeds another command.
  isSubstituted: boolean
  // Its stdout goes to a file or /dev/null.
  isRedirected: boolean
  // The pipeline stages after this one.
  after: Simple[]
}

const WRAPPERS = new Set(['env', 'time', 'sudo', 'command', 'exec', 'nice', 'nohup'])
const KEYWORDS = new Set(['if', 'then', 'else', 'elif', 'while', 'until', 'do', '!', '{'])
// Stdout into a file or /dev/null; `2>` and `>&2` still leave it in the transcript.
const STDOUT_REDIRECT = /(^|[^0-9&>])>(?!&)|&>|\b1>(?!&)/

// The command with quoted spans, escaped characters, and heredoc bodies as spaces; offsets kept.
const mask = (command: string) => {
  const chars = [...command]
  let quote: string | undefined
  for (let i = 0; i < chars.length; i++) {
    const c = chars[i]
    if (quote) {
      if (c === quote) quote = undefined
      else if (c !== '\n') {
        if (c === '\\' && quote === '"') chars[i + 1] = ' '
        chars[i] = ' '
      }
    } else if (c === '\\') {
      chars[i] = ' '
      if (i + 1 < chars.length && chars[i + 1] !== '\n') chars[i + 1] = ' '
      i++
    } else if (c === "'" || c === '"') quote = c
  }
  let text = chars.join('')
  for (const doc of command.matchAll(/<<-?\s*(['"]?)(\w+)\1[^\n]*\n/g)) {
    const bodyStart = (doc.index ?? 0) + doc[0].length
    const close = new RegExp(String.raw`^\s*${doc[2]}\s*$`, 'm')
    const rest = command.slice(bodyStart)
    const end = close.exec(rest)
    const bodyEnd = bodyStart + (end ? end.index + end[0].length : rest.length)
    text = text.slice(0, bodyStart) + text.slice(bodyStart, bodyEnd).replace(/[^\n]/g, ' ').replace(/\n/g, ' ') + text.slice(bodyEnd)
  }
  return text
}

const unquote = (raw: string) => (raw.match(/(?:[^\s'"]+|'[^']*'|"(?:\\.|[^"\\])*")+/g) ?? []).map(word => word.replace(/'([^']*)'|"((?:\\.|[^"\\])*)"/g, '$1$2'))

const commandWords = (raw: string) => {
  const words = unquote(raw)
  let i = 0
  while (i < words.length) {
    const word = words[i] ?? ''
    if (/^\w+=/.test(word) || KEYWORDS.has(word)) i++
    else if (WRAPPERS.has(word)) {
      i++
      while ((words[i] ?? '').startsWith('-')) i++
    } else break
  }
  return words.slice(i)
}

// `}` closes a group only as its own word; `${VAR}` stays one word.
const SEPARATOR = /\|\||&&|;|\||(?<![>&])&(?![>&])|\n|\$\(|\(|\)|`|(?<=^|[\s;])\}(?=[\s;]|$)/g

// Every simple command in `command`, in order.
export const simpleCommands = (command: string): Simple[] => {
  const masked = mask(command)
  const found: (Simple & { sep: string })[] = []
  const stack: string[] = []
  let start = 0
  const push = (end: number, sep: string) => {
    const text = masked.slice(start, end)
    if (text.trim()) {
      found.push({
        words: commandWords(command.slice(start, end)),
        isSubstituted: stack.includes('$(') || stack.includes('`'),
        isRedirected: STDOUT_REDIRECT.test(text),
        after: [],
        sep,
      })
    }
  }
  for (const match of masked.matchAll(SEPARATOR)) {
    const sep = match[0]
    const at = match.index ?? 0
    push(at, sep)
    if (sep === '$(' || sep === '(') stack.push(sep)
    else if (sep === ')') stack.pop()
    else if (sep === '`') stack[stack.length - 1] === '`' ? stack.pop() : stack.push('`')
    start = at + sep.length
  }
  push(masked.length, '')
  for (let i = found.length - 1; i >= 0; i--) {
    const stage = found[i]
    const next = found[i + 1]
    if (stage && next && stage.sep === '|') stage.after = [next, ...next.after]
  }
  return found
}

// The command name without its directory.
export const base = (word: string | undefined) => (word ?? '').replace(/^.*\//, '')
