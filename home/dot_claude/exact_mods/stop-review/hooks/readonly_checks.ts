import type { EngineInterface } from 'claude-code'

// The final answer's format checks: a `Checked:` list after a change, no work parked under a heading the report has no
// list for, and no question to the user outside `Decision needed:`. They need no model, so they run without an advisorModel.

// Edits here are not part of the user's change.
export const IGNORED = /^(\/private)?\/(tmp|var\/folders)\/|\/\.claude\/(plans|projects)\//
// A `Checked` header line, bold or not, with or without a colon. A sentence that starts with "Checked" is not one.
const CHECKED = /^[\s>*_#-]*Checked(?:\*\*|__)?(?:[ \t]*\([^)\n]*\))?(?::|[ \t]*$)/m
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
// The user's question, kept on purpose: the last prose paragraph, before any list, starts with this marker.
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
// The working tree's state: changed paths, a hash of the tracked diff, and a hash of untracked contents.
const SNAPSHOT =
  'git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 3\n' +
  'git --no-optional-locks status --porcelain=v1\n' +
  'git diff HEAD --no-ext-diff --binary 2>/dev/null | git hash-object --stdin\n' +
  'git ls-files --others --exclude-standard | git hash-object --stdin-paths | git hash-object --stdin'

// The ~/AGENTS.md §1 limits on acting without asking, kept whole so a send-back never pushes past them.
export const STEP =
  'a step ~/AGENTS.md §1 makes part of the task (in the request\'s scope, and either named by the request or reversible and ' +
  'changing nothing outside this machine that the request did not name; never a §5 action or a step the user asked you to ' +
  'ask about first)'

// Each message states what the check found, what to do now, and the ~/AGENTS.md rule it follows, with the limits that rule sets on acting,
// so the one send-back ends with the work done rather than reworded.
const MESSAGE =
  'Files changed this turn, and the final message has no `Checked:` list. Run any check the change still needs, ' +
  'then list each claim under `Checked:` with its command and result, or a `file:line` (~/AGENTS.md §3 step 8).'

const QUESTION =
  `The final message ends with a question outside \`Decision needed:\`. If its answer is ${STEP}, do it now. ` +
  'Keep a question only for a decision that is the user\'s (§1), last, under `Decision needed:`, with your pick. ' +
  'Put an out-of-scope step under `Proposed:`, and one you cannot do now under `Open:` with its blocker.'

const deferral = (heading: string) =>
  `The final message lists work under \`${heading}\`, which the ~/AGENTS.md §3 step 8 report has no slot for. ` +
  `Do each item that is ${STEP} now. ` +
  'Put an item that is the user\'s decision (§1) under `Decision needed:` with your pick, an out-of-scope item under `Proposed:`, ' +
  'and an item you cannot do now under `Open:` with its blocker. Steps for the user to run belong in the answer itself, under no such heading.'

// A function declaration: the engine follows $ past an import only into one.
export async function snapshot($: EngineInterface) {
  const run = await $.process.run(['sh', '-c', SNAPSHOT], { timeoutMs: 20000 })
  return run.exitCode === 0 ? run.stdout : undefined
}

const prose = (message: string) => message.replace(/```[\s\S]*?```|~~~[\s\S]*?~~~/g, '').replace(/^[ \t]*>.*$/gm, '').trim()

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

export type Turn = {
  // A main-agent tool ran this turn.
  isActive: boolean
  isAskWanted: boolean
  isListWanted: boolean
  // Files changed this turn; it compares the working tree only when the answer has no `Checked:` list.
  isChanged: () => Promise<boolean>
}

// The messages for what the final answer breaks, in report order.
export const findings = async (message: string, turn: Turn) => {
  const messages: string[] = []
  if (!CHECKED.test(message) && (await turn.isChanged())) messages.push(MESSAGE)
  const deferred = turn.isActive && !turn.isListWanted ? DEFERRED.exec(prose(message)) : null
  if (deferred) messages.push(deferral(deferred[0].trim()))
  const isOpenItem = REPORT_LIST.test(listHeader(message) ?? '')
  if (turn.isActive && !turn.isAskWanted && !marksDecision(message) && !isOpenItem && endsWithQuestion(message)) messages.push(QUESTION)
  return messages
}
