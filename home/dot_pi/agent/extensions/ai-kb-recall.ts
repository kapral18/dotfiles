// Managed by chezmoi (source: home/dot_pi/agent/extensions/ai-kb-recall.ts).
// Shared session context and durable-memory recall for Pi.
//
// Integration extension:
//   - topic + spec resolution comes from `,agent-memory status --json --session-id <id>`
//     (single source of truth: scripts/agent_memory.py / hook_common.py)
//   - retrieval + ranking comes from `,ai-kb search` (scripts/ai_kb.py)
//   - Pi lifecycle state and persisted per-session recall dedupe stay here
//
// Injection points, all delivered through before_agent_start:
//   0. Shared session context: session_context.py supplies the verification prefix,
//      topic buckets or active topic spec/worklog, and named-topic BM25 warm-start.
//   1. Verification prefix re-injection after compaction or material context growth.
//      Context fill + compaction track real decay better than a turn count.
//   2. Per-turn (every substantive prompt): query = the user's actual prompt — the
//      highest-relevance signal — deduped against capsules already injected this session.
//      The same pass appends the shared precision-first correction directive when a
//      prompt reads as a user correction, matching executable_perturn_recall.py.
//
// Both share the same relevance gate as the Python warm-start: `,ai-kb search
// --workspace-gate` keeps only capsules local to this workspace or scoped
// domain/universal, so a large/cross-project KB cannot stuff context.
//
// Worklog capture: tool_result events are forwarded to the shared
// worklog_dispatcher.sh (same payload shape as the Copilot adapter), so pi
// sessions feed the same <topic>.worklog.jsonl trail as every other harness.

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent"
import { spawn } from "node:child_process"
import { mkdir, readFile, writeFile } from "node:fs/promises"
import { homedir } from "node:os"
import { dirname, join } from "node:path"

const EXEC_TIMEOUT_MS = 6_000
// The shared hook can spend up to 5s warming embeddings, then 6s on BM25.
const SESSION_CONTEXT_TIMEOUT_MS = 15_000
const SEARCH_STDOUT_MAX_BYTES = 1024 * 1024
const SESSION_CONTEXT_HOOK = "session_context.py"
const WARMSTART_LIMIT = 3
const PERTURN_LIMIT = 3
const SEARCH_FETCH = 6
const QUERY_MAX_CHARS = 600
const BODY_MAX_CHARS = 240
const MIN_PROMPT_CHARS = 12
const DETECT_MAX_CHARS = 20_000
const CONJUNCTION_WINDOW_CHARS = 160
const PREFIX_MAX_CHARS = 3000
const AI_AGENT_DEPTH = "AI_AGENT_DEPTH"
// bm25/warm-start relative relevance floor: after the top hit, drop any hit whose
// bm25Relevance() is worse than this fraction of the best hit's magnitude. Absolute
// score floors are fragile (bm25 magnitude shifts with query length and corpus), but the
// *ratio* to the best hit is stable, so a far-worse hit is reliably off-topic. Verified
// against live `,ai-kb search` output: on an on-topic query the relevant capsule scored
// ~2-3x the cross-domain noise; 0.6 cleanly separates them. Hybrid/per-turn does not use
// this floor — it trims on cosine (PERTURN_COSINE_FLOOR_FRACTION) because rrf is rank-flat.
const RELEVANCE_FLOOR_FRACTION = 0.6
// Absolute relevance gate for per-turn (hybrid) retrieval: unless the BEST hit's
// cosine similarity clears this bar, suppress the entire per-turn block. The relative
// floor only compares hits to each other, so on a prompt with no KB overlap it still
// keeps a cluster of equally-irrelevant capsules (RRF rank-position is relevance-blind:
// rank 1 on a junk query scores like rank 1 on a perfect one). cosine_score is the only
// absolute, cross-query-comparable signal. Calibrated against live `,ai-kb search`:
// on-topic top hits scored 0.58-0.81, off-topic top hits 0.44-0.48 — 0.55 sits in the
// gap. Gate the TOP hit only with this absolute bar; the per-row tail is trimmed by a
// cosine floor relative to the top hit (PERTURN_COSINE_FLOOR_FRACTION), not a second
// absolute threshold — a fixed per-row cosine floor would wrongly drop legitimate
// secondary hits (which overlap off-topic rows in absolute terms), but a floor scaled
// to *this query's* best hit adapts: strict when the top hit is strong, lenient when
// the whole result set is weakly-and-equally related.
const PERTURN_MIN_TOP_COSINE = 0.55
// Per-turn (hybrid) tail trim: after the absolute top-hit gate passes, drop any hit
// whose cosine is below this fraction of the top hit's cosine. Replaces the rrf-based
// relative floor for hybrid, which is toothless because rrf_score is rank-position-
// derived and nearly constant (~0.12-0.13 across all hits), so a 0.6-of-best rrf floor
// trims nothing. cosine is the only cross-query-comparable signal. Verified against live
// `,ai-kb search` over 5 queries: 0.85 drops cross-domain noise riding on a weak top hit
// (e.g. chezmoi query top 0.61 -> floor 0.52 drops 0.49 ,ai-kb-internals capsules) while
// preserving genuine secondary matches when the result set is uniformly weak.
const PERTURN_COSINE_FLOOR_FRACTION = 0.85
// Re-inject the verification prefix once context-window fill has grown by at least this
// many percentage points since it was last injected (decay proxy). Compaction forces a
// re-inject regardless, since it summarizes/drops the prior prefix.
const PREFIX_REINJECT_DELTA_PCT = 20

// Same verification-discipline core the tmux wrap pastes manually and that
// session_context.py injects for cursor-agent/claude. Read from the deployed file
// (single source of truth) on each turn it is re-injected (see PREFIX_REINJECT_DELTA_PCT).
//
// prefix.txt holds only the discipline core; framing is owned per consumer because
// placement differs. pi appends before_agent_start messages AFTER the user message
// (agent-session.js builds [user, ...extension messages]), so here the user's prompt
// is ABOVE this injected block — the framing must point backward, never claim a prompt
// follows.
async function readPrefix(pi: ExtensionAPI): Promise<string> {
  const configHome = process.env.XDG_CONFIG_HOME || `${process.env.HOME ?? ""}/.config`
  const path = `${configHome}/tmux/agent_prompts/prefix.txt`
  const result = await pi.exec("cat", [path], { timeout: EXEC_TIMEOUT_MS })
  if (result.killed || result.code !== 0) return ""
  const core = result.stdout.trim().slice(0, PREFIX_MAX_CHARS)
  if (!core) return ""
  return `${core}\n\nApply the discipline above to the user's prompt.`
}

interface MemoryStatus {
  workspace: string
  selected_topic: string
  session_key: string
  is_named_topic: boolean
  spec_file: string
  spec_exists: boolean
}

interface Capsule {
  id?: string
  title?: string
  body?: string
  kind?: string
  scope?: string
  workspace_path?: string
  bm25_score?: number | null
  rrf_score?: number | null
  cosine_score?: number | null
}

interface RecallSessionState {
  contextKey: string
  seenPath: string
  injectedIds: Set<string>
  initialContextDone: boolean
  lastPrefixPercent: number | null
  forceReinject: boolean
}

interface SessionContextResult {
  ok: boolean
  context: string
}

type SearchMode = "bm25" | "hybrid"
type AgentDepth = "fast" | "balanced" | "deep"
type CorrectionSignal = "unrequested-action" | "omission-correction" | "unverified-claim" | "guessed-not-tested" | "repeat-failure"

interface RecallProfile {
  enabled: boolean
  limit: number
  fetch: number
  queryChars: number
  bodyChars: number
  timeoutMs: number
}

const BALANCED_PROFILE: RecallProfile = {
  enabled: true,
  limit: PERTURN_LIMIT,
  fetch: SEARCH_FETCH,
  queryChars: QUERY_MAX_CHARS,
  bodyChars: BODY_MAX_CHARS,
  timeoutMs: EXEC_TIMEOUT_MS,
}
const RECALL_PROFILES: Record<AgentDepth, RecallProfile> = {
  fast: { enabled: false, limit: 0, fetch: 0, queryChars: 0, bodyChars: 0, timeoutMs: 0 },
  balanced: BALANCED_PROFILE,
  deep: { enabled: true, limit: 5, fetch: 12, queryChars: 1200, bodyChars: 360, timeoutMs: 9_000 },
}

function agentDepth(): AgentDepth {
  const value = (process.env[AI_AGENT_DEPTH] ?? "").trim().toLowerCase()
  return value === "fast" || value === "deep" ? value : "balanced"
}

// bm25 relevance signal. In bm25 mode rrf_score is rank-derived and nearly constant, so
// bm25_score (SQLite's negative log score, smaller = better) is the real signal; negate
// so "larger = better". Hybrid never uses this (it trims on cosine and returns early).
function bm25Relevance(row: Capsule): number | null {
  const raw = row.bm25_score
  if (raw == null) return null
  return -raw
}

// Drop hits whose relevance is far below the best hit's. Keeps the top hit always;
// rows missing the score field (shouldn't happen for the active mode) are kept so a
// scoring gap never silently swallows everything. bm25 mode assumes rows are
// best-first (single-signal ranking); hybrid mode does NOT (see below).
function applyRelevanceFloor(rows: Capsule[], mode: SearchMode): Capsule[] {
  if (!rows.length) return rows
  // Absolute top-hit gate (hybrid/per-turn only): if the best hit isn't semantically
  // close to the query, nothing in the KB is relevant — suppress the whole block rather
  // than inject a cluster of equally-irrelevant capsules the relative floor would keep.
  //
  // Hybrid rows are fused-rank order (RRF + MMR), NOT best-cosine-first, so rows[0] is
  // not necessarily the best cosine — scan every row for the best available cosine
  // instead. Rows missing cosine_score are excluded from the max (no evidence), but
  // still fail-open in the tail trim below.
  if (mode === "hybrid") {
    const cosines = rows.map((row) => row.cosine_score).filter((c): c is number => typeof c === "number")
    if (!cosines.length) return []
    const topCosine = Math.max(...cosines)
    if (topCosine < PERTURN_MIN_TOP_COSINE) return []
    if (rows.length <= 1) return rows
    // Tail trim relative to the best cosine. rrf_score is rank-flat in hybrid, so the
    // rrf relative floor below cannot separate on-topic from cross-domain hits; cosine
    // can. Preserves the original fused/MMR presentation order — filtering never
    // reorders rows. Any row missing cosine is kept (fail-open).
    const cosineFloor = topCosine * PERTURN_COSINE_FLOOR_FRACTION
    return rows.filter((row) => {
      const c = row.cosine_score
      return c == null || c >= cosineFloor
    })
  }
  if (rows.length <= 1) return rows
  let best: number | null = null
  for (const row of rows) {
    const s = bm25Relevance(row)
    if (s != null) {
      best = s
      break
    }
  }
  if (best == null || best <= 0) return rows
  const floor = best * RELEVANCE_FLOOR_FRACTION
  return rows.filter((row) => {
    const s = bm25Relevance(row)
    return s == null || s >= floor
  })
}

function collapse(text: string, max: number): string {
  const flat = text.replace(/\s+/g, " ").trim()
  if (flat.length <= max) return flat
  return flat.slice(0, max).trimEnd() + "…"
}

const UNREQUESTED_ACTION_NEGATION_RE = /\b(?:never|do\s+not|i\s+didn['’]?t\s+ask|undo|revert)\b/i
const WHY_DID_YOU_RE = /\bwhy\s+(?:the\s+(?:fuck|hell)\s+)?(?:did|would)\s+you\b/i
const ARE_YOU_SURE_RE = /\bare\s+you\s+sure\b/i
const SURE_FOLLOWUP_RE = /\bhave\s+you\s+(?:tried|tested|verified|checked)\b|\bor\b[\s\S]{0,200}?\bguess/i

const CORRECTION_PATTERNS: Array<[CorrectionSignal, RegExp]> = [
  ["unrequested-action", /\bi\s+didn['’]?t\s+ask\s+(?:you\s+)?(?:to|for)\b|\bi\s+never\s+asked\b/i],
  ["omission-correction", /\bwhy\s+did(?:n['’]?t|\s+not)\s+you\b|\bwhy\s+did\s+you\s+not\b/i],
  ["unverified-claim", /\bdid\s+you\s+(?:really|actually)\s+(?:measure|test|verify|check|run|try)\b/i],
  ["unverified-claim", /\bhallucinat\w*\b/i],
  ["guessed-not-tested", /\b(?:you\s+guessed|did\s+you\s+guess|was\s+that\s+a\s+guess|or\s+(?:did\s+)?you\s+guess)\b/i],
  ["guessed-not-tested", /\binstead\s+of\s+(?:testing|verifying|measuring|checking|proving)\b/i],
  ["unrequested-action", /\b(?:never|don['’]?t|do\s+not)\s+(?:commit|push|delete|force|do\s+(?:that|this)\s+again)\b/i],
  ["repeat-failure", /\b(?:still|again)\s+(?:broken|wrong|failing|not\s+working|doesn['’]?t\s+work)\b/i],
  ["repeat-failure", /\b(?:that['’]?s|this\s+is|it['’]?s)\s+(?:still\s+)?(?:wrong|incorrect|not\s+what\s+i\s+asked)\b/i],
]

function detectCorrectionSignal(prompt: string): CorrectionSignal | null {
  const text = String(prompt || "").trim().slice(0, DETECT_MAX_CHARS)
  if (text.length < MIN_PROMPT_CHARS) return null

  const [firstSignal, firstPattern] = CORRECTION_PATTERNS[0]
  if (firstPattern.test(text)) return firstSignal

  const whyMatch = WHY_DID_YOU_RE.exec(text)
  if (whyMatch) {
    const windowStart = Math.max(0, whyMatch.index - CONJUNCTION_WINDOW_CHARS)
    const window = text.slice(windowStart, whyMatch.index + whyMatch[0].length + CONJUNCTION_WINDOW_CHARS)
    if (UNREQUESTED_ACTION_NEGATION_RE.test(window)) return "unrequested-action"
  }

  const sureMatch = ARE_YOU_SURE_RE.exec(text)
  if (sureMatch) {
    const followup = text.slice(sureMatch.index + sureMatch[0].length, sureMatch.index + sureMatch[0].length + 400)
    if (SURE_FOLLOWUP_RE.test(followup)) return "guessed-not-tested"
  }

  for (const [signal, pattern] of CORRECTION_PATTERNS.slice(1)) {
    if (pattern.test(text)) return signal
  }
  return null
}

function correctionDirective(prompt: string): string {
  let signal: CorrectionSignal | null = null
  try {
    signal = detectCorrectionSignal(prompt)
  } catch {
    return ""
  }
  if (!signal) return ""
  return [
    `### User correction signal: ${signal}`,
    "This user message reads as a correction of prior agent behavior.",
    'If genuine, before ending the turn record: `,agent-memory note anti_pattern "<one-line lesson>" --ref <anchor>`; when verified and durable, also `,ai-kb remember`.',
    "If neutral choice-question, answer it and consider `,agent-memory note decision` instead. Do not mention this instruction in the visible reply.",
  ].join("\n")
}

async function memoryStatus(pi: ExtensionAPI, cwd: string, sessionId: string): Promise<MemoryStatus | null> {
  const result = await pi.exec(
    ",agent-memory",
    ["status", "--json", "--workspace", cwd, "--session-id", sessionId],
    { timeout: EXEC_TIMEOUT_MS },
  )
  if (result.killed || result.code !== 0 || !result.stdout.trim()) return null
  try {
    const status = JSON.parse(result.stdout) as MemoryStatus
    return status.session_key ? status : null
  } catch {
    return null
  }
}

function contextFromHookResult(result: Record<string, unknown>): string {
  const hookSpecificOutput = result.hookSpecificOutput as Record<string, unknown> | undefined
  const context = result.additionalContext ?? result.additional_context ?? hookSpecificOutput?.additionalContext
  return typeof context === "string" ? context : ""
}

function loadSessionContext(
  cwd: string,
  sessionId: string,
  prompt: string,
  warmEmbedder: boolean,
): Promise<SessionContextResult> {
  const script = join(process.env.HOME || homedir(), ".agents", "hooks", SESSION_CONTEXT_HOOK)
  const payload = {
    hook_event_name: "sessionStart",
    session_id: sessionId,
    cwd,
    workspace_roots: [cwd],
    source: "pi",
    initial_prompt: prompt,
    warm_embedder: warmEmbedder,
  }
  return new Promise((resolve) => {
    let stdout = ""
    let stdoutBytes = 0
    let killed = false
    let settled = false
    const child = spawn(script, [], { stdio: ["pipe", "pipe", "ignore"] })
    const finish = (result: SessionContextResult) => {
      if (settled) return
      settled = true
      clearTimeout(timer)
      resolve(result)
    }
    const timer = setTimeout(() => {
      killed = true
      child.kill("SIGKILL")
    }, SESSION_CONTEXT_TIMEOUT_MS)

    child.stdout.on("data", (chunk: Buffer) => {
      stdoutBytes += chunk.length
      if (stdoutBytes > SEARCH_STDOUT_MAX_BYTES) {
        killed = true
        child.kill("SIGKILL")
        return
      }
      stdout += chunk.toString()
    })
    child.stdin.on("error", () => {})
    child.on("error", () => finish({ ok: false, context: "" }))
    child.on("close", (code) => {
      if (killed || code !== 0) {
        finish({ ok: false, context: "" })
        return
      }
      try {
        const result = JSON.parse(stdout || "{}") as Record<string, unknown>
        finish({ ok: true, context: contextFromHookResult(result) })
      } catch {
        finish({ ok: false, context: "" })
      }
    })
    child.stdin.end(JSON.stringify(payload))
  })
}

function seenFileFor(specFile: string, sessionId: string): string {
  return join(dirname(specFile), `.recall-seen-${sessionId}.json`)
}

function contextKeyFor(status: MemoryStatus): string {
  return `${status.selected_topic}\0${status.spec_file}`
}

async function loadSeen(path: string): Promise<Set<string>> {
  try {
    const value = JSON.parse(await readFile(path, "utf8"))
    if (!Array.isArray(value)) return new Set()
    return new Set(value.filter((id): id is string => typeof id === "string"))
  } catch {
    return new Set()
  }
}

async function saveSeen(path: string, seen: Set<string>): Promise<void> {
  try {
    await mkdir(dirname(path), { recursive: true })
    await writeFile(path, JSON.stringify([...seen].sort()))
  } catch {
    // Recall-state persistence is best effort; never block a turn.
  }
}

async function searchCapsules(
  workspace: string,
  query: string,
  mode: SearchMode,
  profile: RecallProfile = BALANCED_PROFILE,
): Promise<Capsule[]> {
  if (!profile.enabled) return []
  const flat = collapse(query, profile.queryChars)
  if (!flat) return []
  const searchArgs = [
    "search",
    "--query-stdin",
    "--limit",
    String(profile.fetch),
    "--mode",
    mode,
    "--workspace",
    workspace,
    "--workspace-gate",
    "--json",
  ]
  const result = await runSearch(flat, searchArgs, mode === "hybrid", profile.timeoutMs)
  if (result.killed || result.code !== 0 || !result.stdout.trim()) return []
  try {
    const rows = JSON.parse(result.stdout)
    return Array.isArray(rows) ? applyRelevanceFloor(rows as Capsule[], mode) : []
  } catch {
    return []
  }
}

interface SearchExecResult {
  stdout: string
  code: number
  killed: boolean
}

function runSearch(query: string, args: string[], connectOnly: boolean, timeoutMs: number): Promise<SearchExecResult> {
  return new Promise((resolve) => {
    let stdout = ""
    let stdoutBytes = 0
    let killed = false
    let settled = false
    const child = spawn(",ai-kb", args, {
      env: connectOnly ? { ...process.env, AI_EMBED_CONNECT_ONLY: "1" } : process.env,
      stdio: ["pipe", "pipe", "ignore"],
    })
    const finish = (result: SearchExecResult) => {
      if (settled) return
      settled = true
      clearTimeout(timer)
      resolve(result)
    }
    const timer = setTimeout(() => {
      killed = true
      child.kill("SIGKILL")
    }, timeoutMs)
    child.stdout.on("data", (chunk: Buffer) => {
      stdoutBytes += chunk.length
      if (stdoutBytes > SEARCH_STDOUT_MAX_BYTES) {
        killed = true
        child.kill("SIGKILL")
        return
      }
      stdout += chunk.toString()
    })
    child.stdin.on("error", () => {})
    child.on("error", () => finish({ stdout: "", code: 1, killed }))
    child.on("close", (code) => finish({ stdout, code: code ?? 1, killed }))
    child.stdin.end(query)
  })
}

// Fire-and-forget worklog forwarding to the shared dispatcher. The dispatcher
// detaches its recorder, so this only needs to deliver the payload; every
// failure is swallowed (worklog capture must never break a tool call).
const WORKLOG_OUTPUT_MAX_CHARS = 2_000

function recordWorklog(payload: Record<string, unknown>): void {
  const home = process.env.HOME ?? ""
  if (!home) return
  const dispatcher = join(home, ".agents", "hooks", "worklog_dispatcher.sh")
  try {
    const child = spawn(dispatcher, [], { stdio: ["pipe", "ignore", "ignore"] })
    child.on("error", () => {})
    child.stdin.on("error", () => {})
    child.stdin.end(JSON.stringify(payload))
  } catch {
    // fail open
  }
}

function toolResultText(content: unknown): string {
  if (!Array.isArray(content)) return ""
  const parts: string[] = []
  for (const item of content) {
    const text = (item as { text?: unknown })?.text
    if (typeof text === "string" && text) parts.push(text)
  }
  return parts.join("\n").slice(0, WORKLOG_OUTPUT_MAX_CHARS)
}

// Cross-repo scope gating is owned by `,ai-kb search --workspace-gate` (same
// contract as the shared hooks). Skips capsules already injected this session.
function gateAndFormat(
  rows: Capsule[],
  seen: Set<string>,
  limit: number,
  bodyChars: number = BODY_MAX_CHARS,
): string[] {
  const lines: string[] = []
  for (const row of rows) {
    if (lines.length >= limit) break
    const id = row.id ?? ""
    if (id && seen.has(id)) continue
    const title = collapse(row.title ?? "", 200)
    if (!title) continue
    if (id) seen.add(id)
    const kind = row.kind || "note"
    const body = collapse(row.body ?? "", bodyChars)
    lines.push(body ? `- **${title}** (${kind}): ${body}` : `- **${title}** (${kind})`)
  }
  return lines
}

export default async function (pi: ExtensionAPI) {
  // Disable cleanly if the CLIs are not on PATH (e.g. partial install).
  const probe = await pi.exec(",ai-kb", ["--help"], { timeout: EXEC_TIMEOUT_MS })
  if (probe.code !== 0) {
    console.warn("[ai-kb-recall] ,ai-kb not found in PATH — extension disabled")
    return
  }

  const stateBySession = new Map<string, RecallSessionState>()
  const depth = agentDepth()
  const perturnProfile = RECALL_PROFILES[depth]

  pi.on("session_start", (_event, ctx) => {
    stateBySession.delete(ctx.sessionManager.getSessionId())
  })

  // session_compact cannot inject context (only before_agent_start can), so it flags a
  // forced re-inject that the next before_agent_start consumes.
  pi.on("session_compact", (_event, ctx) => {
    const state = stateBySession.get(ctx.sessionManager.getSessionId())
    if (!state) return
    state.forceReinject = true
    state.lastPrefixPercent = null
  })

  // Worklog capture: mirror the Copilot adapter's postToolUse payload so the
  // shared recorder treats pi like every other harness. Fail-open by design.
  pi.on("tool_result", (event, ctx) => {
    try {
      recordWorklog({
        hook_event_name: event.isError ? "postToolUseFailure" : "postToolUse",
        session_id: ctx.sessionManager.getSessionId(),
        cwd: ctx.cwd,
        tool_name: event.toolName,
        tool_input: event.input,
        tool_output: toolResultText(event.content),
        status: event.isError ? "failure" : "success",
      })
    } catch {
      // fail open
    }
  })

  pi.on("before_agent_start", async (event, ctx) => {
    try {
      const sessionId = ctx.sessionManager.getSessionId()
      let state = stateBySession.get(sessionId)
      let sharedContext = state
        ? { ok: true, context: "" }
        : await loadSessionContext(ctx.cwd, sessionId, event.prompt, perturnProfile.enabled)
      if (!sharedContext.ok) {
        console.warn("[ai-kb-recall] shared session context hook failed; using local recall fallback")
      }
      const status = await memoryStatus(pi, ctx.cwd, sessionId)
      if (!status) {
        if (!sharedContext.context) return
        return {
          message: {
            customType: "ai-kb-recall",
            content: sharedContext.context,
            display: true,
          },
        }
      }
      const workspace = status.workspace || ctx.cwd
      const contextKey = contextKeyFor(status)
      const seenPath = seenFileFor(status.spec_file, status.session_key)
      if (state && state.contextKey !== contextKey) {
        sharedContext = await loadSessionContext(ctx.cwd, sessionId, event.prompt, perturnProfile.enabled)
        if (!sharedContext.ok) {
          console.warn("[ai-kb-recall] shared session context hook failed after topic change; using local recall fallback")
        }
      }
      if (!state || state.contextKey !== contextKey) {
        state = {
          contextKey,
          seenPath,
          injectedIds: await loadSeen(seenPath),
          initialContextDone: sharedContext.ok,
          lastPrefixPercent: null,
          forceReinject: false,
        }
        stateBySession.set(sessionId, state)
      }
      const seenCount = state.injectedIds.size
      const blocks: string[] = sharedContext.context ? [sharedContext.context] : []

      // 0. Verification prefix: warm-start, after a compaction, or once context fill has
      //    grown PREFIX_REINJECT_DELTA_PCT points since the last injection.
      const usage = ctx.getContextUsage()
      const percent = usage && usage.percent != null ? usage.percent : null
      if (state.lastPrefixPercent == null && percent != null && !state.forceReinject) {
        state.lastPrefixPercent = percent
      }
      const grewEnough =
        state.lastPrefixPercent != null &&
        percent != null &&
        percent - state.lastPrefixPercent >= PREFIX_REINJECT_DELTA_PCT
      if (!state.initialContextDone || state.forceReinject || grewEnough) {
        const prefix = await readPrefix(pi)
        if (prefix) {
          blocks.push(prefix)
          state.forceReinject = false
          if (percent != null) state.lastPrefixPercent = percent
        }
      }

      // 1. Fallback warm-start when the shared session-context hook is unavailable.
      if (!state.initialContextDone) {
        state.initialContextDone = true
        if (status.is_named_topic && status.spec_exists) {
          const spec = await pi.exec("cat", [status.spec_file], { timeout: EXEC_TIMEOUT_MS })
          const specText = spec.code === 0 ? spec.stdout : ""
          if (specText.trim()) {
            // Warm-start query is the spec text (keyword-dense), and runs at session
            // start where the embedder may be cold/slow — bm25 keeps it fast and
            // dependency-light, floored on bm25_score.
            const rows = await searchCapsules(workspace, specText, "bm25")
            const lines = gateAndFormat(rows, state.injectedIds, WARMSTART_LIMIT)
            if (lines.length) {
              blocks.push(
                ["### Relevant Learnings (,ai-kb)", "Surfaced from durable memory for this topic; verify before relying on them.", ...lines].join(
                  "\n",
                ),
              )
            }
          }
        }
      }

      // 2. Per-turn: highest-relevance retrieval using the actual prompt (pi-only capability).
      const prompt = typeof event.prompt === "string" ? event.prompt : ""
      if (prompt.trim().length >= MIN_PROMPT_CHARS) {
        // Per-turn uses the actual prompt and hybrid retrieval: the vector lane + MMR
        // suppress capsules that only share surface words with the prompt, and rrf_score
        // is the floor signal. This is where cross-domain lexical noise was leaking in.
        const rows = await searchCapsules(workspace, prompt, "hybrid", perturnProfile)
        const lines = gateAndFormat(
          rows,
          state.injectedIds,
          perturnProfile.limit,
          perturnProfile.bodyChars,
        )
        if (lines.length) {
          blocks.push(
            ["### Relevant Learnings for this request (,ai-kb)", "Matched to your prompt; verify before relying on them.", ...lines].join("\n"),
          )
        }
        const directive = correctionDirective(prompt)
        if (directive) blocks.push(directive)
      }

      if (state.injectedIds.size !== seenCount) await saveSeen(state.seenPath, state.injectedIds)
      if (!blocks.length) return
      return {
        message: {
          customType: "ai-kb-recall",
          content: blocks.join("\n\n"),
          display: true,
        },
      }
    } catch (err) {
      // Fail open: never block a turn on a recall error.
      console.warn("[ai-kb-recall] unexpected error; skipping injection", err)
      return
    }
  })
}
