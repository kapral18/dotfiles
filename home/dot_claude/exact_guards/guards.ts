import { appendFileSync, mkdirSync } from 'node:fs'
import { homedir } from 'node:os'
import { join } from 'node:path'

import { handle as behaviorMap } from './behavior-map-guard'
import { context, endSession, type HookInput, type HookOutput, main, run, sessionPath, stateDir } from './hook'
import { handle as sop } from './sop-guard'

const WRITERS = new Set(['Bash', 'Edit', 'Write', 'NotebookEdit'])

// A guard that throws answers nothing, so the next guard and `,task` still run.
const attempt = (guard: (input: HookInput) => HookOutput, input: HookInput): HookOutput => {
  try {
    return guard(input)
  } catch {
    return undefined
  }
}

// intent-guard's core: `,task` answers the same payload with hook JSON of its own.
const task = (raw: string): HookOutput => {
  const done = run([join(homedir(), 'bin', ',task'), 'hook', 'claude'], { stdin: raw, timeoutMs: 15000 })
  try {
    const out = JSON.parse(done.stdout) as HookOutput
    return out?.hookSpecificOutput ? out : undefined
  } catch {
    return undefined
  }
}

// Every call that ran, and every failed Bash call, by any agent, one JSON line each: stop-review reads the lines added since its last answer to see the turn's edits.
const logCall = (input: HookInput): HookOutput => {
  const path = input.tool_input?.notebook_path ?? input.tool_input?.file_path
  mkdirSync(stateDir(), { recursive: true })
  appendFileSync(sessionPath('stop-review', input.session_id, 'calls'), `${JSON.stringify({ tool: input.tool_name, path: typeof path === 'string' ? path : undefined, agent: input.agent_id })}\n`)
  return undefined
}

// Every guard runs from this one hook per event: Claude Code shows one refusal reason, so the first refusal ends the chain
// before a later guard spends its once-per-session refusal unseen. `,task` goes last, so a refused call leaves no snapshot.
const handle = (input: HookInput, raw: string): HookOutput => {
  if (input.hook_event_name === 'SessionEnd') {
    endSession('sop-guard', input.session_id)
    endSession('behavior-map-guard', input.session_id)
    endSession('stop-review', input.session_id)
    return undefined
  }
  const writer = WRITERS.has(input.tool_name ?? '')
  if (input.hook_event_name === 'PreToolUse') {
    for (const guard of writer ? [sop, behaviorMap] : []) {
      const out = attempt(guard, input)
      if (out) return out
    }
    return input.agent_id === undefined ? task(raw) : undefined
  }
  // A shell command that fails may still have written files; a failed edit wrote nothing.
  if (input.hook_event_name === 'PostToolUse' || input.tool_name === 'Bash') attempt(logCall, input)
  const notes = [input.agent_id === undefined ? task(raw) : undefined, writer ? attempt(behaviorMap, input) : undefined]
    .map(out => out?.hookSpecificOutput.additionalContext)
    .filter((text): text is string => typeof text === 'string' && text !== '')
  return notes.length ? context(input, notes.join('\n\n')) : undefined
}

await main(handle)
