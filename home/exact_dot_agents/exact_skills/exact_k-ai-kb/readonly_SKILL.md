---
name: k-ai-kb
description: "Use for automatic staged recall, correction learning, and durable knowledge persistence."
---

# Durable Knowledge And Learning

`,ai-kb` owns durable capsules; current task decisions and handoffs belong in the active `/tmp/specs` topic.
Automatic root hooks retain startup/per-turn retrieval, relevance/workspace filters, and candidate staging.
They emit a pointer once per session-topic binding; later retrieval updates the staged set silently.
Retrieval is deterministic plumbing, not a new orchestration stage or a model invocation.
Do not disable retrieval, correction capture, or learning merely to prevent agent recursion.

Record genuine corrections with `,agent-memory note anti_pattern` and decisions with `,agent-memory note decision`.
Include evidence references. Notes are learning inputs, not already-verified durable claims.
Before delivery, persist the session's verified reusable insights in one final learning batch.
If no durable insight exists, there is nothing to write. Keep unverified/session-only notes in topic history.
Do not launch a scribe per correction or per turn. Do not reopen Verify to manufacture learning evidence.

## Root moves

Only the active root/main session follows this section; a delegated leaf skips it and returns findings to its parent.
Process a new staged pointer through one memory-band `k-agent-smol` judge packet.
Use `~/.agents/skills/k-ai-kb/references/smol-operator.md`; admit only its compact returned lines. Reuse admitted memory.
Further recall needs a material new question or task shift, not another prompt or compaction alone.
No staged data: query recall only when prior knowledge could change the current decision.
Record packet IDs and results in the active topic; do not relaunch active/completed packets.
After final verification, send the verified learning batch to one memory-band scribe packet with existing evidence.
The scribe owns search-first deduplication, deliberate metadata, and write readback; it does not re-verify the task.
Memory workers MUST NOT invoke agents, perform their own recall workflow, audit another worker, or resume after returning.
Do not use an expensive model as a substitute for an unavailable memory lane or invoke another harness as a fallback.

## Inline fallback

When delegation is forbidden or unavailable, the root performs the same admission/write mechanics inline.
Read only the scoped candidate set and relevant topic state; retain compact admitted facts, not capsule dumps.
Follow `~/.agents/skills/k-ai-kb/references/smol-operator.md` and `~/.agents/skills/k-ai-kb/references/cli.md`.
Use deterministic tools; do not invoke another model. Preserve search-first dedupe, metadata, evidence, and readback.
If the CLI or required evidence is unavailable, retain the pending learning in topic history and report that specific gap.
Do not retry failed memory packets automatically or block unrelated delivery on a memory-service outage.
