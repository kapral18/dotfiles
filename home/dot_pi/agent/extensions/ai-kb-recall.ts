// Managed by chezmoi (source: home/dot_pi/agent/extensions/ai-kb-recall.ts).
// Durable-memory recall for pi, matching the Cursor/Claude sessionStart warm-start
// and adding pi's per-turn retrieval (Cursor's beforeSubmitPrompt cannot inject context).
//
// Integration extension:
//   - topic + spec resolution comes from `,agent-memory status --json --session-id <id>`
//     (single source of truth: scripts/agent_memory.py / hook_common.py)
//   - retrieval + ranking comes from `,ai-kb search` (scripts/ai_kb.py)
//   - Pi lifecycle state and persisted per-session recall dedupe stay here
//
// Injection points, all via before_agent_start (pi's only context-injection hook):
//   0. Verification prefix: injected at session start, then re-injected when it has
//      decayed — either after a compaction (session_compact summarizes/drops it) or once
//      context-window fill has grown by PREFIX_REINJECT_DELTA_PCT points since the last
//      injection. Context fill + compaction track real decay far better than a turn count
//      (turn size varies wildly). The tmux wrap pastes the same prefix.txt manually;
//      session_context.py injects it once for cursor-agent/claude. before_agent_start is
//      pi's only context-injection hook, so session_compact merely flags a forced
//      re-inject that the next before_agent_start consumes.
//   1. Warm-start (first prompt of a session): query = the active topic spec, gated to a
//      deliberate named topic with a non-empty <topic>.txt. Mirrors session_context.py.
//   2. Per-turn (every substantive prompt): query = the user's actual prompt — the
//      highest-relevance signal — deduped against capsules already injected this session.
//
// Both share the same relevance gate as the Python warm-start: keep only capsules local to
// this workspace or scoped domain/universal, so a large/cross-project KB cannot stuff context.

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent"
import { spawn } from "node:child_process"
import { mkdir, readFile, writeFile } from "node:fs/promises"
import { dirname, join } from "node:path"

const EXEC_TIMEOUT_MS = 6_000
const SEARCH_STDOUT_MAX_BYTES = 1024 * 1024
const WARMSTART_LIMIT = 3
const PERTURN_LIMIT = 3
const SEARCH_FETCH = 6
const QUERY_MAX_CHARS = 600
const BODY_MAX_CHARS = 240
const MIN_PROMPT_CHARS = 12
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
const CROSS_PROJECT_SCOPES = new Set(["domain", "universal"])

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
  seenPath: string
  injectedIds: Set<string>
  warmStartDone: boolean
  lastPrefixPercent: number | null
  forceReinject: boolean
}

type SearchMode = "bm25" | "hybrid"
type AgentDepth = "fast" | "balanced" | "deep"

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

function seenFileFor(specFile: string, sessionId: string): string {
  return join(dirname(specFile), `.recall-seen-${sessionId}.json`)
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

async function warmEmbedder(pi: ExtensionAPI, depth: AgentDepth): Promise<void> {
  if (depth === "fast") return
  const home = process.env.HOME ?? ""
  if (!home) return
  await pi.exec("python3", [join(home, "lib", ",ai-kb", "embed_client.py"), "ensure", "--timeout", "4"], {
    timeout: 5_000,
  })
}

// Same gate as session_context.py: workspace-local capsules, or deliberately cross-project
// (domain/universal) ones. Skips capsules already injected this session.
function gateAndFormat(
  rows: Capsule[],
  workspace: string,
  seen: Set<string>,
  limit: number,
  bodyChars: number = BODY_MAX_CHARS,
): string[] {
  const lines: string[] = []
  for (const row of rows) {
    if (lines.length >= limit) break
    const sameWorkspace = (row.workspace_path ?? "") === workspace
    const scope = row.scope ?? ""
    if (!sameWorkspace && !CROSS_PROJECT_SCOPES.has(scope)) continue
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

  pi.on("session_start", async () => {
    await warmEmbedder(pi, depth)
  })

  // session_compact cannot inject context (only before_agent_start can), so it flags a
  // forced re-inject that the next before_agent_start consumes.
  pi.on("session_compact", (_event, ctx) => {
    const state = stateBySession.get(ctx.sessionManager.getSessionId())
    if (!state) return
    state.forceReinject = true
    state.lastPrefixPercent = null
  })

  pi.on("before_agent_start", async (event, ctx) => {
    try {
      const sessionId = ctx.sessionManager.getSessionId()
      const status = await memoryStatus(pi, ctx.cwd, sessionId)
      if (!status) return
      const workspace = status.workspace || ctx.cwd
      const seenPath = seenFileFor(status.spec_file, status.session_key)
      let state = stateBySession.get(sessionId)
      if (!state || state.seenPath !== seenPath) {
        state = {
          seenPath,
          injectedIds: await loadSeen(seenPath),
          warmStartDone: false,
          lastPrefixPercent: null,
          forceReinject: false,
        }
        stateBySession.set(sessionId, state)
      }
      const seenCount = state.injectedIds.size
      const blocks: string[] = []

      // 0. Verification prefix: warm-start, after a compaction, or once context fill has
      //    grown PREFIX_REINJECT_DELTA_PCT points since the last injection.
      const usage = ctx.getContextUsage()
      const percent = usage && usage.percent != null ? usage.percent : null
      const grewEnough =
        state.lastPrefixPercent != null &&
        percent != null &&
        percent - state.lastPrefixPercent >= PREFIX_REINJECT_DELTA_PCT
      if (!state.warmStartDone || state.forceReinject || grewEnough) {
        const prefix = await readPrefix(pi)
        if (prefix) {
          blocks.push(prefix)
          state.forceReinject = false
          if (percent != null) state.lastPrefixPercent = percent
        }
      }

      // 1. Warm-start: once per session, named-topic + spec only (parity with Cursor/Claude).
      if (!state.warmStartDone) {
        state.warmStartDone = true
        if (status.is_named_topic && status.spec_exists) {
          const spec = await pi.exec("cat", [status.spec_file], { timeout: EXEC_TIMEOUT_MS })
          const specText = spec.code === 0 ? spec.stdout : ""
          if (specText.trim()) {
            // Warm-start query is the spec text (keyword-dense), and runs at session
            // start where the embedder may be cold/slow — bm25 keeps it fast and
            // dependency-light, floored on bm25_score.
            const rows = await searchCapsules(workspace, specText, "bm25")
            const lines = gateAndFormat(rows, workspace, state.injectedIds, WARMSTART_LIMIT)
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
          workspace,
          state.injectedIds,
          perturnProfile.limit,
          perturnProfile.bodyChars,
        )
        if (lines.length) {
          blocks.push(
            ["### Relevant Learnings for this request (,ai-kb)", "Matched to your prompt; verify before relying on them.", ...lines].join("\n"),
          )
        }
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
