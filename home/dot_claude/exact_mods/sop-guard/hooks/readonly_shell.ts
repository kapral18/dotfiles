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

// A heredoc operator and the rest of its line; its body starts on the next line.
// `<<-` lets tabs indent the closing line; quotes and backslashes in the end word (`<<'EOF'`, `<<E\OF`, `<<E"O"F`) are removed.
const HEREDOC = /<<(-?)\s*((?:\\.|'[^']*'|"(?:\\.|[^"\\])*"|[^\s;&|<>()'"\\])+)[^\n]*\n/y
const escapeRegExp = (text: string) => text.replace(/[.*+?^${}()|[\]\\-]/g, '\\$&')
// A command starts after a separator, an opening `(` or `{`, a `)` that is not a substitution's, or a keyword.
const isCommandStart = (before: string, isCommandParen: (at: number) => boolean) => {
  const trimmed = before.replace(/[ \t]+$/, '')
  return isCommandParen(trimmed.length - 1) || /(?:^|[;&|({\n]|(?:^|[\s;&|({])(?:if|elif|while|until|then|do|else|time|coproc|!))$/.test(trimmed)
}
// `((` is arithmetic when the `)` that closes it at depth 0 is followed by `)`: `for ((i=0; i<n; i++))` is,
// `((cd a; ls) )` is two subshells.
const closesArithmetic = (command: string, from: number) => {
  let depth = 0
  for (let j = from; j < command.length; j++) {
    if (command[j] === '(') depth++
    else if (command[j] === ')') {
      if (depth === 0) return command[j + 1] === ')'
      depth--
    }
  }
  return false
}

// The command with quoted spans, escaped characters, and heredoc bodies as spaces; offsets kept.
// A `<<` counts as a heredoc only where the shell reads one: outside quotes, or inside a `$(` within double quotes.
// Its body is blanked as one block, so a quote inside it never opens a span.
// `comments` holds where each comment starts, so its words are never read as arguments.
const mask = (command: string) => {
  const chars = command.split('')
  const bodies: [number, number][] = []
  const comments: number[] = []
  // A `)` after which a command can follow: one that closes nothing (a case pattern), a function's `()`,
  // a `(pattern)` after `in` or `;;`, or a subshell. A glob's `*(N)` is none of these.
  const commandParens = new Set<number>()
  // Where each open plain `(` starts.
  const parenOpens: number[] = []
  // Characters taken by a backslash escape; an escaped newline is removed, so the character before its backslash counts.
  const escaped = new Set<number>()
  const before = (j: number) => {
    while (j >= 1 && command[j] === '\n' && escaped.has(j)) j -= 2
    return j
  }
  // Open spans, innermost last: a quote, a `$'` ANSI-C quote, a `$(` substitution, a `$((` or `((` arithmetic,
  // a `${` expansion, a `[[` test, or a `(` group.
  const stack: string[] = []
  const isQuoted = () => stack.includes('"') || stack.includes("'") || stack.includes("$'")
  for (let i = 0; i < chars.length; i++) {
    const body = bodies.find(([start, end]) => i >= start && i < end)
    if (body) {
      for (; i < body[1]; i++) chars[i] = ' '
      i--
      continue
    }
    const c = chars[i]
    const top = stack[stack.length - 1]
    const wasQuoted = isQuoted()
    if (top === "'") {
      if (c === "'") stack.pop()
    } else if (c === '\\') {
      // An escaped character is data; an escaped newline joins two lines into one command.
      chars[i] = ' '
      if (i + 1 < chars.length) chars[i + 1] = ' '
      escaped.add(i + 1)
      i++
      continue
    } else if (top === "$'") {
      if (c === "'") stack.pop()
    } else if (c === '$' && chars[i + 1] === '(') {
      // `$((` opens arithmetic, where `<<` is a shift; `$(` opens a substitution.
      const open = chars[i + 2] === '(' ? '$((' : '$('
      stack.push(open)
      if (wasQuoted) for (let j = i; j < i + open.length; j++) chars[j] = ' '
      i += open.length - 1
      continue
    } else if (top === '"') {
      if (c === '"') stack.pop()
      else if (c === '$' && chars[i + 1] === '{') {
        // A `${` in double quotes opens a span where `"` and `${` nest; `'` stays literal, as in zsh, the Bash tool's shell.
        stack.push('${"')
        chars[i] = chars[i + 1] = ' '
        i++
        continue
      }
    } else if (top === '${"') {
      if (c === '}') stack.pop()
      else if (c === '"') stack.push(c)
      else if (c === '$' && chars[i + 1] === '{') {
        stack.push('${"')
        chars[i] = chars[i + 1] = ' '
        i++
        continue
      }
    } else {
      const isArithmetic = stack.includes('$((') || stack.includes('((')
      // Inside `${ }` and `[[ ]]`, parentheses are patterns, not groups, and `<<` is no heredoc.
      const isBrace = top === '${'
      const isTest = top === '[['
      if (!isArithmetic && !isBrace && !isTest && command.startsWith('<<', i) && command[i - 1] !== '<' && command[i + 2] !== '<') {
        HEREDOC.lastIndex = i
        const doc = HEREDOC.exec(command)
        if (doc) {
          const bodyStart = i + doc[0].length
          const close = new RegExp(`^${doc[1] ? '\\t*' : ''}${escapeRegExp((doc[2] ?? '').replace(/\\(.)|['"]/g, '$1'))}$`, 'm')
          const end = close.exec(command.slice(bodyStart))
          bodies.push([bodyStart, end ? bodyStart + end.index + end[0].length : command.length])
        }
      }
      // A `#` at a word start in the original text, not after an escaped character, starts a comment.
      // Inside `${ }` it never does; inside `[[ ]]` only after a space (`[[ $l =~ ^(#|$) ]]` holds no comment).
      const previous = before(i - 1)
      const isWordStart = previous < 0 || ((isTest ? /\s/ : /[\s;|&()<>]/).test(command[previous] ?? '') && !escaped.has(previous))
      if (c === '#' && isWordStart && !isBrace && !isArithmetic) {
        // A comment runs to the end of its line; a quote inside it opens nothing.
        comments.push(i)
        for (; i + 1 < chars.length && chars[i + 1] !== '\n'; i++) chars[i + 1] = ' '
        continue
      }
      // `$$` is the shell's PID, so a quote after it is a plain quote.
      if (c === '$' && chars[i + 1] === '$') {
        i++
        continue
      }
      if (c === '$' && chars[i + 1] === "'") {
        stack.push("$'")
        i++
        continue
      }
      if (c === '$' && chars[i + 1] === '{') {
        stack.push('${')
        i++
        continue
      }
      // `[[ ` opens a test only in command position; `]]` closes it only as its own word, so `[[:space:]]` stays inside.
      if (c === '[' && chars[i + 1] === '[' && /\s/.test(command[i + 2] ?? '') && !isBrace && isCommandStart(command.slice(0, i), at => commandParens.has(at))) {
        stack.push('[[')
        i++
        continue
      }
      if (isTest && c === ']' && chars[i + 1] === ']' && /\s/.test(command[i - 1] ?? '') && /^(?:[\s;&|)]|$)/.test(command.slice(i + 2, i + 3))) {
        stack.pop()
        i++
        continue
      }
      if (c === "'" || c === '"') stack.push(c)
      else if (isBrace && c === '}') stack.pop()
      else if ((isBrace || isTest) && (c === '(' || c === ')')) chars[i] = ' '
      else if (c === '(' && chars[i + 1] === '(' && closesArithmetic(command, i + 2)) {
        stack.push('((')
        i++
      } else if (c === '(') {
        stack.push('(')
        parenOpens.push(i)
      } else if (c === ')' && (top === '$((' || top === '((') && chars[i + 1] === ')') {
        stack.pop()
        if (wasQuoted && isQuoted()) chars[i] = chars[i + 1] = ' '
        i++
        continue
      } else if (c === ')' && top === '$(') stack.pop()
      else if (c === ')' && top === '(') {
        stack.pop()
        const open = parenOpens.pop() ?? -1
        const head = command.slice(0, open)
        if (open === i - 1 || /(?:\bin|;;|;&)\s*$/.test(head) || isCommandStart(head, at => commandParens.has(at))) commandParens.add(i)
      } else if (c === ')') commandParens.add(i)
    }
    // Text inside a quote, newlines too, is data; the outermost quote marks stay so words keep their edges.
    if (wasQuoted && isQuoted()) chars[i] = ' '
  }
  return { text: chars.join(''), comments }
}

const unquote = (raw: string) => (raw.replace(/\\\n/g, '').match(/(?:[^\s'"]+|'[^']*'|"(?:\\.|[^"\\])*")+/g) ?? []).map(word => word.replace(/'([^']*)'|"((?:\\.|[^"\\])*)"/g, '$1$2'))

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
  const { text: masked, comments } = mask(command)
  const found: (Simple & { sep: string })[] = []
  const stack: string[] = []
  let start = 0
  const push = (end: number, sep: string) => {
    const text = masked.slice(start, end)
    if (text.trim()) {
      found.push({
        words: commandWords(command.slice(start, comments.find(at => at >= start && at < end) ?? end)),
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
