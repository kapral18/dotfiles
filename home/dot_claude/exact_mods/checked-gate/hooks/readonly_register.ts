import type { EngineInterface, Register } from 'claude-code'

// Edits here are not part of the user's change.
const IGNORED = /^(\/private)?\/(tmp|var\/folders)\/|\/\.claude\/(plans|projects)\//
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
const asksToAsk = (prompt: string) => [...prompt.matchAll(ASK_ME)].some(match => !isRefused(prompt.slice(0, match.index)))
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
const LIST_WANTED =
  /(?:^|[.?!;:]\s*|\b(?:please|and|then|also|just|can you|could you)\s+)(?:list|show(?: me)?|give me|tell me)\b[^.?!\n]{0,30}\b(?:next steps?|gaps|remaining|left|to-?dos?|follow[- ]?ups?)\b|\bwhat(?:['’]s| is| are)\s+(?:next|left|remaining|missing)\b|\bwhat remains\b|\bhand[- ]?off\b|(?:["'“‘`]\s*(?:\*\*)?(?:known gaps|not done|not yet done|(?:still|left) to do|remaining(?: work| steps| items)?|next(?: steps?)?|follow[- ]?ups?|to-?dos?|unverified|not verified|pending|deferred)\b|\b(?:known gaps|next steps?|follow[- ]?ups?|to-?dos?|unverified|not verified|deferred)[:"'”’`*]*\s+(?:list|section|heading|block)\b)/i
// The working tree's state: changed paths, a hash of the tracked diff, and a hash of untracked contents.
const SNAPSHOT =
  'git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 3\n' +
  'git --no-optional-locks status --porcelain=v1\n' +
  'git diff HEAD --no-ext-diff --binary 2>/dev/null | git hash-object --stdin\n' +
  'git ls-files --others --exclude-standard | git hash-object --stdin-paths | git hash-object --stdin'

// Each message states what the hook found and points at the ~/AGENTS.md rule; the rule text lives only there.
const MESSAGE = 'Files changed this turn, and the final message has no `Checked:` list (~/AGENTS.md §3 step 8).'

// The send-back's reply replaces the answer the user reads, so it must be the whole current answer.
const FINAL = 'Your reply replaces your last answer: follow the ~/AGENTS.md §8 rule for a send-back.'

const QUESTION = 'The final message ends with a question outside `Decision needed:`. Apply the ~/AGENTS.md §1 rule on questions.'

const deferral = (heading: string) =>
  `The final message lists work under \`${heading}\`; the ~/AGENTS.md §3 step 8 report has no such list. Apply step 8 to each item.`

const snapshot = async ($: EngineInterface) => {
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

export const register: Register = on => {
  let isEdited = false
  let isActive = false
  let isAskWanted = false
  let isListWanted = false
  // Each check sends a turn back at most once per Stop chain: a send-back's continuation has stop_hook_active set.
  let sent = new Set<string>()
  // undefined: no Bash call yet this turn; null: the snapshot failed.
  let baseline: string | null | undefined
  // The last Stop paused on a subagent or workflow still in flight.
  let isPaused = false

  on('turn.start', ($, e, next) => {
    // A continuation after a send-back starts with empty text, and the task notice that wakes a paused turn starts with its tag;
    // both keep the turn's state. A typed prompt starts a new turn.
    const isContinuation = e.text === '' || (isPaused && e.text.startsWith('<task-notification>'))
    isPaused = false
    if (isContinuation) return next(e)
    isEdited = false
    isActive = false
    isAskWanted = asksToAsk(e.text)
    isListWanted = LIST_WANTED.test(e.text)
    baseline = undefined
    return next(e)
  })

  on('tool.call', { tool: ['Edit', 'Write', 'NotebookEdit'] }, async ($, e, next) => {
    const ran = await next(e)
    const path = 'notebook_path' in e ? e.notebook_path : e.file_path
    // A subagent's edit changes the tree too, so it counts as an edit.
    if (ran.deny === undefined && ran.isError !== true && !IGNORED.test(path)) isEdited = true
    return ran
  }).catch(($, e, next) => next(e))

  on('tool.call', { tool: 'Bash' }, async ($, e, next) => {
    if (!isEdited && baseline === undefined) baseline = (await snapshot($).catch(() => undefined)) ?? null
    return next(e)
  }).catch(($, e, next) => next(e))

  on('tool.call', ($, e, next) => {
    if (e.agentId === undefined) isActive = true
    return next(e)
  }).catch(($, e, next) => next(e))

  on('classic.Stop', async ($, e, next) => {
    const message = e.last_assistant_message ?? ''
    const below = await next(e)
    if (!e.stop_hook_active) sent = new Set()
    // A subagent or workflow still in flight wakes the session when it ends, so this Stop pauses the turn and does not end it.
    // A background shell task does not count: a server never ends, and it would switch the checks off for the session.
    isPaused = (e.background_tasks ?? []).some(task => task.type === 'subagent' || task.type === 'workflow')
    if (isPaused) return below
    const messages = new Map<string, string>()
    if (!CHECKED.test(message) && !sent.has('checked')) {
      let isChanged = isEdited
      if (!isChanged && typeof baseline === 'string') {
        const now = await snapshot($)
        isChanged = now !== undefined && now !== baseline
      }
      if (isChanged) messages.set('checked', MESSAGE)
    }
    const deferred = isActive && !isListWanted ? DEFERRED.exec(prose(message)) : null
    if (deferred) messages.set('deferred', deferral(deferred[0].trim()))
    const isOpenItem = REPORT_LIST.test(listHeader(message) ?? '')
    if (isActive && !isAskWanted && !marksDecision(message) && !isOpenItem && endsWithQuestion(message)) messages.set('question', QUESTION)
    const fresh = [...messages].filter(([kind]) => !sent.has(kind))
    if (fresh.length === 0) return below
    for (const [kind] of fresh) sent.add(kind)
    const block = [...fresh.map(([, text]) => text), FINAL].join('\n\n')
    return { ...below, block: below.block ? `${below.block}\n\n${block}` : block }
  }).catch(($, e, next) => next(e))
}
