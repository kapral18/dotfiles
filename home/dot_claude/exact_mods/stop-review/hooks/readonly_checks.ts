import type { EngineInterface } from 'claude-code'

// The final answer's format checks: a `Checked:` list after a change, no work parked under a heading the report has no
// list for, no question to the user outside `Decision needed:`, and the §8 word budget. They need no model, so they run without an advisorModel.

// Edits here are not part of the user's change.
export const IGNORED = /^(\/private)?\/(tmp|var\/folders)\/|\/\.claude\/(plans|projects)\//
// A `Checked` header line, bold or not, with or without a colon. A sentence that starts with "Checked" is not one.
const CHECKED = /^[\s>*_#+-]*Checked(?:\*\*|__)?(?:[ \t]*\([^)\n]*\))?(?::|[ \t]*$)/m
const ASK_ME = /\bask(?:ing)? (?:me|us)\b/gi
// What ends the text before "ask me" when it refuses: a negation up to three words back ("don't even need to ask me"),
// or stop/quit/avoid up to two words back, not across and/then/to/but/or/just/instead.
// "Stop (constantly) asking me" refuses; "stop and ask me" and "don't hesitate to ask me" invite.
const NEGATED = /(?:(?:n['’]t|\b(?:do|does|did|wo|ca|need|should|could|would|must)nt|\bnot|\bnever|\bno need|\bwithout)(?:\s+(?!hesitate\b)\w+){0,3}|\b(?:stop|quit|avoid)(?:\s+(?!(?:and|then|to|but|or|just|instead)\b)\w+){0,2})\s*$/i
// A negation in a condition ("if not sure, ask me") still invites.
const CONDITION = /^\s*(?:if|unless|when|whenever)\b/i
const isRefused = (before: string) => NEGATED.test(before) && !CONDITION.test(before.split(/[.!?;,\n]/).pop() ?? '')
// The user's prompt asks to be asked, so the question check stays quiet.
export const asksToAsk = (prompt: string) => [...prompt.matchAll(ASK_ME)].some(match => !isRefused(prompt.slice(0, match.index)))
// The line that opens the user's question, kept on purpose.
const DECISION = /^[\s>*_#-]*Decision needed(\*\*)?:/
const LIST_ITEM = /^\s*(?:[-*+]|\d+[.)])\s/m
// A question under these report lists is an open item, not a question to the user.
const REPORT_LIST = /^[\s>*_#-]*(?:\*\*)?(?:Open|Proposed)(\*\*)?:/
const LIST_ONLY = /^\s*(?:[-*+]|\d+[.)])\s.*(?:\n(?:\s*(?:[-*+]|\d+[.)])\s|[ \t]+\S).*)*\s*$/
// A heading the §3 report has no slot for, under which doable work gets parked: "Known gaps:", "Next steps:", "Unverified:".
// Only a heading line counts (plain, `#`, or bold), not a bullet. A one-word label (Next, Remaining, Pending) counts only alone on its line.
// A heading whose whole list is "none", "n/a", or "nothing" passes.
const DEFERRED =
  /^[ \t]*(?:#{1,6}[ \t]+)?(?:\*\*|__)?(?:(?:Known gaps|Not done|Not yet done|(?:Still|Left) to do|Remaining (?:work|steps|items)|(?:Suggested |Recommended |Possible )?(?:Next steps?|Follow[- ]?ups?)|TODOs?|Unverified|Not verified|Deferred)(?:[ \t]*\([^)\n]*\))?(?:\*\*|__)?(?::(?:\*\*|__)?|[ \t]*$)|(?:Next|Remaining|Pending)(?:\*\*|__)?:(?:\*\*|__)?[ \t]*$)(?![*_ \t—–-]*(?:\n\s*(?:(?:[-*+]|\d+[.)])[ \t]+)?)?[*_]*(?:none|n\/a|nothing)[*_.]*[ \t]*$(?!\n[ \t]*\S))/im
// The user asked for such a list: "what's left?", "list the next steps", "show me the gaps", a handoff,
// or a prompt that names the heading itself (`a "Known gaps:" list`, `"Next steps" section`).
export const LIST_WANTED =
  /(?:^|[.?!;:]\s*|\b(?:please|and|then|also|just|can you|could you)\s+)(?:list|show(?: me)?|give me|tell me)\b[^.?!\n]{0,30}\b(?:next steps?|gaps|remaining|left|to-?dos?|follow[- ]?ups?)\b|\bwhat(?:['’]s| is| are)\s+(?:next|left|remaining|missing)\b|\bwhat remains\b|\bhand[- ]?off\b|(?:["'“‘`]\s*(?:\*\*)?(?:known gaps|not done|not yet done|(?:still|left) to do|remaining(?: work| steps| items)?|next(?: steps?)?|follow[- ]?ups?|to-?dos?|unverified|not verified|pending|deferred)\b|\b(?:known gaps|next steps?|follow[- ]?ups?|to-?dos?|unverified|not verified|deferred)[:"'”’`*]*\s+(?:list|section|heading|block)\b)/i
// ~/AGENTS.md §8 budgets, lists and tables included: a change report, else an investigation.
const CHANGE_BUDGET = 250
const BUDGET = 200
// The working tree's state: changed paths, a hash of the tracked diff, and a hash of untracked contents.
const SNAPSHOT =
  'git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 3\n' +
  'git --no-optional-locks status --porcelain=v1\n' +
  'git diff HEAD --no-ext-diff --binary 2>/dev/null | git hash-object --stdin\n' +
  'git ls-files --others --exclude-standard | git hash-object --stdin-paths | git hash-object --stdin'

// The ~/AGENTS.md §1 limits on acting without asking, kept whole so a send-back never pushes past them; ,task's hook_stop words them the same.
export const STEP =
  'a step ~/AGENTS.md §1 makes part of the task (named by the request, or reversible and changing nothing outside this machine the request did not name, ' +
  'when it is in the request\'s scope (fixes from a review the request ran on the user\'s own work count) or fixes a defect in the change\'s impact (§3 step 1); ' +
  'or a §3 step 7 cleanup k-cleanup allows; never a §5 action §5 does not allow, ' +
  'a live check §3 step 4 keeps for the user\'s ask, or a step the user asked you to ask about first)'

// What ~/AGENTS.md §3 step 8 puts under `Proposed:`, one wording for every send-back.
export const PROPOSED =
  'an item outside the request\'s scope that fixes no defect in the change\'s impact (§3 steps 1 and 8) under `Proposed:`'

// Where ~/AGENTS.md §3 step 8 puts a live check it does not let the agent offer.
const UNVERIFIED = 'a claim only a live check could settle under `Open:` with that check as its blocker (§3 step 8)'

// Each message states what the check found, what to do now, and the ~/AGENTS.md rule it follows, with the limits that rule sets on acting,
// so the one send-back ends with the work done rather than reworded.
const MESSAGE =
  'Files changed this turn, and the final message has no `Checked:` list. Run any check §3 steps 3-4 call for that the change still needs, ' +
  'then list one item per Done-when item or changed behavior under `Checked:` with its command and result, or a `file:line`, and each fact\'s verified `[C<n>]`; ' +
  'put a claim only a live check could settle under `Open:` with that check as its blocker (~/AGENTS.md §3 step 8).'

// A word holds a letter or digit, so table rules and list bullets do not count.
const words = (text: string) => text.split(/\s+/).filter(token => /[\p{L}\p{N}]/u.test(token)).length

const overBudget = (count: number, budget: number) =>
  `The final message is ${count} words; ~/AGENTS.md §8 caps this answer at ${budget}, lists and tables included. ` +
  'Cut it to fit: group `Checked:` items by Done-when item or behavior, drop narration the diff already shows, ' +
  'and keep every fact the user needs to act (evidence, paths, numbers, `Open:` and `Decision needed:` items); facts win over the budget. ' +
  'If the user\'s prompt asked for detail, a write-up, or a long list, keep the answer as it is.'

const QUESTION =
  `The final message ends with a question outside \`Decision needed:\`. If its answer is ${STEP}, do it now. ` +
  'Keep a question only for what needs the user\'s judgment (§1), last, under `Decision needed:`, with your pick. ' +
  `Put ${PROPOSED}, ${UNVERIFIED}, and one you cannot do now under \`Open:\` with its blocker.`

const deferral = (heading: string) =>
  `The final message lists work under \`${heading}\`, which the ~/AGENTS.md §3 step 8 report has no slot for. ` +
  `Do each item that is ${STEP} now. ` +
  `Put an item that needs the user's judgment (§1) under \`Decision needed:\` with your pick, ${PROPOSED}, ${UNVERIFIED}, ` +
  'and an item you cannot do now under `Open:` with its blocker. Steps for the user to run belong in the answer itself, under no such heading; ' +
  'cleanup is never one of them (§3 step 7).'

// A function declaration: the engine follows $ past an import only into one.
export async function snapshot($: EngineInterface) {
  const run = await $.process.run(['sh', '-c', SNAPSHOT], { timeoutMs: 20000 })
  return run.exitCode === 0 ? run.stdout : undefined
}

type Container = { kind: 'quote' } | { kind: 'list'; indent: number; isEmpty: boolean }
const fenceMarker = (text: string) => text.match(/^ {0,3}(`{3,}|~{3,})(.*)$/)
const opensFence = (marker: RegExpMatchArray | null) => marker !== null && (marker[1][0] !== '`' || !marker[2].includes('`'))
const listMarker = (text: string) => text.match(/^( {0,3}(?:[-+*]|\d{1,9}[.)]))( +|$)/)
const thematicBreak = (text: string) => /^ {0,3}(?:(?:\*[ \t]*){3,}|(?:-[ \t]*){3,}|(?:_[ \t]*){3,})$/.test(text)
const isBlank = (text: string) => /^ *$/.test(text)
const HTML_BLOCK = /^ {0,3}<\/?(?:address|article|aside|base|basefont|blockquote|body|caption|center|col|colgroup|dd|details|dialog|dir|div|dl|dt|fieldset|figcaption|figure|footer|form|frame|frameset|h[1-6]|head|header|hr|html|iframe|legend|li|link|main|menu|menuitem|nav|noframes|ol|optgroup|option|p|param|search|section|summary|table|tbody|td|tfoot|th|thead|title|tr|track|ul)(?:[ \t]|\/?>|$)/i
const htmlBlockEnd = (text: string, isParagraph: boolean): RegExp | undefined => {
  if (/^ {0,3}<!--/.test(text)) return /-->/
  if (/^ {0,3}<\?/.test(text)) return /\?>/
  if (/^ {0,3}<!\[CDATA\[/.test(text)) return /\]\]>/
  if (/^ {0,3}<![A-Z]/.test(text)) return />/
  const raw = text.match(/^ {0,3}<(pre|script|style|textarea)(?:[ \t>]|$)/i)
  if (raw) return new RegExp(`</${raw[1]}>`, 'i')
  if (HTML_BLOCK.test(text)) return /^ *$/
  if (!isParagraph && /^ {0,3}(?:<\/[A-Za-z][A-Za-z0-9-]*[ \t]*>|<[A-Za-z][A-Za-z0-9-]*(?:[ \t]+[A-Za-z_:][\w.:-]*(?:[ \t]*=[ \t]*(?:[^"'=<>` \t]+|'[^']*'|"[^"]*"))?)*[ \t]*\/?>)[ \t]*$/.test(text)) return /^ *$/
  return undefined
}
// Matched paragraphs have stricter list interruption rules than unmatched containers.
const interruptsParagraph = (text: string) =>
  isBlank(text) || opensFence(fenceMarker(text)) || thematicBreak(text) || htmlBlockEnd(text, true) !== undefined ||
  /^ {0,3}(?:#{1,6}(?:[ \t]|$)|>|(?:[-+*]|0{0,8}1[.)])[ \t]+[^ \t])/.test(text)

const continueContainers = (line: string, containers: Container[]) => {
  let text = line
  let matched = 0
  for (const container of containers) {
    if (container.kind === 'quote') {
      const quote = text.match(/^ {0,3}> ?/)
      if (!quote) break
      text = text.slice(quote[0].length)
    } else if (isBlank(text)) {
      if (container.isEmpty) break
    } else {
      if (text.match(/^ */)![0].length < container.indent) break
      text = text.slice(container.indent)
      container.isEmpty = false
    }
    matched++
  }
  return { text, matched }
}

const openContainers = (line: string, containers: Container[]) => {
  let text = line
  for (;;) {
    const quote = text.match(/^ {0,3}> ?/)
    if (quote) {
      containers.push({ kind: 'quote' })
      text = text.slice(quote[0].length)
      continue
    }
    const list = listMarker(text)
    if (!list || thematicBreak(text)) return text
    // Empty items use one padding space; five or more spaces leave the rest as content indentation.
    const indent = list[1].length + (list[2].length > 4 || list[0].length === text.length ? 1 : list[2].length)
    containers.push({ kind: 'list', indent, isEmpty: list[0].length === text.length })
    text = text.slice(indent)
  }
}

// Keep original prose lines for report/list checks, but parse container prefixes before recognizing exempt blocks.
const prose = (message: string) => {
  const containers: Container[] = []
  let fence = ''
  let html: RegExp | undefined
  let isParagraph = false
  const lines: string[] = []
  for (const line of message.split('\n')) {
    const expanded = line.replace(/\r$/, '').split('\t').reduce((text, part, index) => text + (index ? ' '.repeat(4 - text.length % 4) : '') + part, '')
    const continued = continueContainers(expanded, containers)
    const isLazy = continued.matched < containers.length && isParagraph && !listMarker(continued.text) && !interruptsParagraph(continued.text)
    if (!isLazy && continued.matched < containers.length) {
      containers.length = continued.matched
      fence = ''
      html = undefined
      isParagraph = false
    }
    const depth = containers.length
    const text = fence || html || isLazy || (isParagraph && !interruptsParagraph(continued.text)) ? continued.text : openContainers(continued.text, containers)
    if (containers.length !== depth) isParagraph = false
    const marker = fenceMarker(text)
    if (fence) {
      if (marker && marker[1][0] === fence[0] && marker[1].length >= fence.length && /^[ \t]*$/.test(marker[2])) fence = ''
      continue
    }
    if (!html && !isLazy && opensFence(marker)) {
      fence = marker![1]
      isParagraph = false
      continue
    }
    if (!html && !isLazy) html = htmlBlockEnd(text, isParagraph)
    const isHtml = html !== undefined
    if (html?.test(text)) html = undefined
    const isSetext = !isLazy && isParagraph && /^ {0,3}(?:=+|-+)[ \t]*$/.test(text)
    isParagraph = !isHtml && !isBlank(text) && !isSetext && !interruptsParagraph(text) && (isParagraph || !/^ {4}/.test(text))
    if (containers.some(container => container.kind === 'quote')) continue
    // A report label may itself be a list item; keep it out of the trailing-list scan.
    lines.push(line.replace(/^[ \t]*[-*+][ \t]+(?=(?:\*\*|__)?(?:Decision needed|Open|Proposed)(?::|\*\*:|__:))/, ''))
  }
  return lines.join('\n').trim()
}

const endsWithQuestion = (message: string) => {
  const lines = prose(message).split('\n')
  return /\?[*_)"'\s]*$/.test(lines[lines.length - 1] ?? '')
}

// The line that heads the trailing list, if the message ends with one.
const listHeader = (message: string) => {
  const lines = prose(message).split('\n')
  let j = lines.length - 1
  if (!LIST_ITEM.test(lines[j] ?? '')) return undefined
  while (j >= 0 && (LIST_ITEM.test(lines[j] ?? '') || /^[ \t]+\S/.test(lines[j] ?? '') || (lines[j] ?? '').trim() === '')) j--
  return lines[j]
}

// A list after the marker counts only when the marker introduces it: a header ending in `:`, or a list already under it.
const marksDecision = (message: string) => {
  const paragraphs = prose(message).split(/\n\s*\n/)
  let isListDropped = false
  while (paragraphs.length > 1 && LIST_ONLY.test(paragraphs[paragraphs.length - 1] ?? '')) {
    paragraphs.pop()
    isListDropped = true
  }
  const last = paragraphs[paragraphs.length - 1] ?? ''
  // A marker on its own line may head the question's paragraph: "**Decision needed:**", a blank line, then the question.
  if (/^[\s>*_#-]*Decision needed[*_]*:[*_\s]*$/.test(paragraphs[paragraphs.length - 2] ?? '')) return true
  return DECISION.test(last) && (!isListDropped || /:[*_\s]*$/.test(last) || LIST_ITEM.test(last))
}

// The answer may put a question to the user: its prose, outside inline code and URLs, holds a `?` or opens a line with the `Decision needed:` marker.
export const asksUser = (message: string) => {
  const text = prose(message).replace(/`[^`\n]*`|\bhttps?:\/\/\S+/g, '')
  return text.includes('?') || text.split('\n').some(line => DECISION.test(line))
}

export type Turn = {
  // A main-agent tool ran this turn, or a task notice started it.
  isActive: boolean
  isAskWanted: boolean
  isListWanted: boolean
  // Files changed this turn; it compares the working tree only when the answer has no `Checked:` list.
  isChanged: () => Promise<boolean>
}

// The messages for what the final answer breaks, in report order.
export const findings = async (message: string, turn: Turn) => {
  const messages: string[] = []
  const isReport = CHECKED.test(prose(message))
  const isUnreported = !isReport && (await turn.isChanged())
  if (isUnreported) messages.push(MESSAGE)
  const deferred = turn.isActive && !turn.isListWanted ? DEFERRED.exec(prose(message)) : null
  if (deferred) messages.push(deferral(deferred[0].trim()))
  const isOpenItem = REPORT_LIST.test(listHeader(message) ?? '')
  if (turn.isActive && !turn.isAskWanted && !marksDecision(message) && !isOpenItem && endsWithQuestion(message)) messages.push(QUESTION)
  if (turn.isActive) {
    const budget = isReport || isUnreported ? CHANGE_BUDGET : BUDGET
    const count = words(prose(message))
    if (count > budget) messages.push(overBudget(count, budget))
  }
  return messages
}
