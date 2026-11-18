// The literal commands of a shell line: one word list per command joined by `;`, `&&`, `||` or a newline.
// Undefined for anything else (expansions, pipes, redirects, a background `&`, globs, heredocs, an assignment prefix):
// the guards make no claim about syntax they do not read.
export const literalInvocations = (source: string): string[][] | undefined => {
  const commands: string[][] = []
  let words: string[] = []
  let word = ''
  let quote = ''
  let started = false
  const finish = () => {
    if (started) words.push(word)
    word = ''
    started = false
  }
  const end = () => {
    finish()
    if (words.length) commands.push(words)
    words = []
  }
  for (let i = 0; i < source.length; i++) {
    const c = source[i] ?? ''
    if (quote === "'") {
      if (c === "'") quote = ''
      else word += c
      continue
    }
    if (c === '\\') {
      const next = source[++i]
      if (next === undefined || next === '\n' || next === '\r') return undefined
      if (quote === '"' && !'"\\$`'.includes(next)) word += '\\'
      word += next
      started = true
      continue
    }
    if (c === '$' || c === '`') return undefined
    if (quote === '"') {
      if (c === '"') quote = ''
      else word += c
      continue
    }
    if (c === "'" || c === '"') {
      quote = c
      started = true
      continue
    }
    if (c === ' ' || c === '\t') {
      finish()
      continue
    }
    if (c === ';' || c === '\n') {
      end()
      continue
    }
    if ((c === '&' || c === '|') && source[i + 1] === c) {
      i++
      end()
      continue
    }
    if ('&|<>()#*?[]{}~\r'.includes(c)) return undefined
    word += c
    started = true
  }
  if (quote) return undefined
  end()
  if (!commands.length || commands.some(command => /^[A-Za-z_][A-Za-z0-9_]*=/.test(command[0] ?? ''))) return undefined
  return commands
}

export const base = (word: string | undefined) => (word ?? '').replace(/^.*\//, '')
