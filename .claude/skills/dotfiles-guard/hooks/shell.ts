export const literalInvocation = (source: string): string[] | undefined => {
  const words: string[] = []
  let word = ''
  let quote = ''
  let started = false
  const finish = () => {
    if (started) words.push(word)
    word = ''
    started = false
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
    if (';&|<>()#*?[]{}~\r\n'.includes(c)) return undefined
    word += c
    started = true
  }
  if (quote) return undefined
  finish()
  if (!words.length || /^[A-Za-z_][A-Za-z0-9_]*=/.test(words[0] ?? '')) return undefined
  return words
}

export const base = (word: string | undefined) => (word ?? '').replace(/^.*\//, '')
