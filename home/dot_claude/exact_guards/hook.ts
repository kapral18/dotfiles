import { createHash } from 'node:crypto'
import { mkdirSync, rmSync, writeFileSync } from 'node:fs'
import { homedir, tmpdir } from 'node:os'
import { join } from 'node:path'

// A Claude Code command-hook payload (PreToolUse, PostToolUse, PostToolUseFailure, SessionEnd).
export type HookInput = {
  session_id: string
  cwd: string
  hook_event_name: string
  tool_name?: string
  tool_input?: Record<string, unknown>
  tool_use_id?: string
  agent_id?: string
}

export type HookOutput = { hookSpecificOutput: Record<string, unknown> } | undefined

export const deny = (reason: string): HookOutput => ({
  hookSpecificOutput: { hookEventName: 'PreToolUse', permissionDecision: 'deny', permissionDecisionReason: reason },
})

export const context = (input: HookInput, text: string): HookOutput => ({
  hookSpecificOutput: { hookEventName: input.hook_event_name, additionalContext: text },
})

export type Ran = { exitCode: number; stdout: string }

export const run = (argv: string[], options: { cwd?: string; stdin?: string; timeoutMs?: number } = {}): Ran => {
  try {
    const stdin = options.stdin === undefined ? 'ignore' : Buffer.from(options.stdin)
    const done = Bun.spawnSync(argv, { cwd: options.cwd, stdin, timeout: options.timeoutMs ?? 15000, stdout: 'pipe', stderr: 'ignore' })
    return { exitCode: done.exitCode ?? 1, stdout: done.stdout.toString() }
  } catch {
    return { exitCode: 127, stdout: '' }
  }
}

// Each fire goes to the guard ledger (`,task guards`) under the session's worktree; a missing `,task` never changes what a guard decides.
export const logFire = (input: HookInput, guard: string, detail: string) => {
  run([join(homedir(), 'bin', ',task'), 'guard', 'log', guard, '--harness', 'claude', '--session', input.session_id, '--detail', detail.slice(0, 200)], { cwd: input.cwd, timeoutMs: 5000 })
}

// Per-session guard state and markers, removed at SessionEnd.
export const stateDir = () => join(tmpdir(), 'claude-guards')
export const safe = (text: string) => text.replace(/[^\w.-]/g, '_')
export const sessionPath = (guard: string, session: string, suffix: string) => join(stateDir(), `${guard}.${safe(session)}.${suffix}`)

// Claims `key` for the session once: true for the first caller, false after, also across parallel hook processes.
export const claimOnce = (guard: string, session: string, key: string) => {
  mkdirSync(stateDir(), { recursive: true })
  try {
    writeFileSync(sessionPath(guard, session, `${createHash('sha256').update(key).digest('hex').slice(0, 32)}.seen`), '', { flag: 'wx' })
    return true
  } catch {
    return false
  }
}

export const endSession = (guard: string, session: string) => {
  const prefix = `${guard}.${safe(session)}.`
  try {
    for (const name of new Bun.Glob(`${prefix}*`).scanSync(stateDir())) rmSync(join(stateDir(), name), { force: true })
  } catch { /* Nothing was saved. */ }
}

// Reads one payload from stdin and prints the answer; a handler that throws answers nothing, so the call goes on.
export const main = async (handle: (input: HookInput, raw: string) => HookOutput) => {
  let out: HookOutput
  try {
    const raw = await Bun.stdin.text()
    out = handle(JSON.parse(raw) as HookInput, raw)
  } catch {
    out = undefined
  }
  process.stdout.write(`${JSON.stringify(out ?? {})}\n`)
}
