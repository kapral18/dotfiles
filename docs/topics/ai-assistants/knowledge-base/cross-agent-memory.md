---
sidebar_position: 3
title: Runtime recall wiring
---

# Cross-agent context and memory

Task continuity and durable knowledge are separate.

## Task handoff

The existing topic spec/worklog and persistent mirror preserve intent and execution state. Keep the root handoff compact: stage, scope/snapshot, decisions, dependencies, active/terminal packets, open questions, and evidence pointers. Raw transcripts/source/logs stay outside root context. After compaction, resume rather than rediscover or relaunch. Startup hooks retain bounded complete topic/worklog artifacts, context-disable sentinels, and harness output envelopes. Per-turn hooks retain topic binding, correction hints, and growth/compaction-gated reinforcement.

## Durable knowledge

Automatic root hooks retain startup BM25 recall, depth-aware per-turn hybrid recall, relevance/workspace filters, embedder warm-up, full candidate staging, and admitted-ID deduplication. One pointer per session-topic binding requests root-owned admission; later retrieval stages silently. Candidate bodies do not enter the main prompt automatically.

Genuine corrections and decisions are captured with `,agent-memory note`. Before delivery, verified reusable insights form one final learning batch. The memory-band operator retains search-first deduplication, metadata, and readback. No scribe per turn/correction, descendant memory worker, or repeated completed packet is allowed. If delegation is forbidden or unavailable, `k-ai-kb` supplies the same mechanics inline; an unavailable CLI leaves pending learning in topic history rather than losing it or retrying indefinitely.

## Harness delivery

Shared Python hooks serve their existing Claude/Codex/Cursor/Copilot/Antigravity/OpenCode adapters. Pi/OMP extensions retain topic/sentinel checks, worklog forwarding, and reinforcement, with matching retrieval/staging behavior and leaf suppression. Managed leaf preambles suppress optional Pi/OMP prompt-context injection; Pi's native child signal also suppresses it. Pi runtime parity does not append the complete root SOP to a managed leaf. The actual harness controls determine enforcement; no universal context-isolation guarantee is inferred from text.

Sources: shared `session_context.py` / `perturn_recall.py`, Pi/OMP `ai-kb-recall.ts`, `runtime-parity.ts`, and `k-ai-kb`. See [hook memory](hook-memory.md) for CLI/topic mechanics.
