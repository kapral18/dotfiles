---
name: k-ai-kb
description: "Use for automatic staged recall, correction learning, and durable knowledge persistence."
---

# Durable Knowledge And Learning

Subagent dispatch: memory — the staged recall judge runs on the memory lane; the root owns admission and persists the final learning batch inline with `,ai-kb remember`.

`,ai-kb` owns durable capsules; current task decisions and handoffs belong in the active `/tmp/specs` topic.
Automatic root hooks retain startup/per-turn retrieval, relevance/workspace filters, and candidate staging.
They emit a pointer once per session-topic binding; later retrieval updates the staged set silently.
Retrieval is deterministic plumbing, not a new orchestration stage or a model invocation.
Do not disable retrieval, correction capture, or learning merely to prevent agent recursion.

Record genuine corrections with `,agent-memory note anti_pattern` and decisions with `,agent-memory note decision`.
Include evidence references. Notes are learning inputs, not already-verified durable claims.
Before delivery, persist the session's verified reusable insights in one final learning batch.
If no durable insight exists, there is nothing to write. Keep unverified/session-only notes in topic history.
Do not persist per correction or per turn. Do not reopen Verify to manufacture learning evidence.

## Root moves

Only the active root/main session follows this section; a delegated leaf skips it and returns findings to its parent.
Process a new staged pointer through one memory-band `k-agent-smol` judge packet. Per-harness profile names live in `~/.config/ai/agent-bands.v1.json` → `harnesses.<h>.agents`.
Launch one memory-band packet for that judgment; the root MUST NOT substitute its own inline recall for that packet absent the documented forbidden/unavailable-lane fallback below; if the lane is unavailable report blocked and use that fallback.
Use `~/.agents/skills/k-ai-kb/references/smol-operator.md`; admit only its compact returned lines. Reuse admitted memory.
Further recall needs a material new question or task shift, not another prompt or compaction alone.
No staged data: query recall only when prior knowledge could change the current decision.
Record packet IDs and results in the active topic; do not relaunch active/completed packets.
After final verification, the root persists the verified learning batch itself with `,ai-kb remember` (Persist below); NEVER through a scribe packet.
Harvest child notes first: `,ai-kb harvest` surfaces `,agent-memory note` rows that delegated children wrote under the packet's topic; they enter the batch only with root-verified evidence.
A harvested child fact enters the batch only when the root re-opens its `--ref` and the quote matches.
`,ai-kb remember` refuses a title collision or near-duplicate embedding on its own; use `--force` only after reading the colliding capsule and deciding it is a different fact.
Memory workers MUST NOT invoke agents, perform their own recall workflow, audit another worker, or resume after returning.
Do not use an expensive model as a substitute for an unavailable memory lane or invoke another harness as a fallback.

## Persist (root, inline)

The root supplies its own final batch of verified reusable insights with evidence anchors.
Process each insight once; do not re-verify the task.

1. Search first: `,ai-kb search "<the insight's literal identifiers>" --limit 5 --json`.
   A stale or wrong capsule on the same point means `--supersedes <its-id>`; a duplicate means stop and record the existing id instead of writing.
2. Write with every metadata field deliberate (`,ai-kb remember --help` is the live interface):
   honest `--kind`, reuse-breadth `--scope` (`--workspace` only for workspace/project), the evidence anchor as `--source`, honest `--confidence`, `--domain` tags.
   A defaulted field is a degraded write; fix it, do not ignore the warning.
3. Front-load literal identifiers (symbols, paths, error strings, flags) in title and body; a future query matches literals, not paraphrase.
4. Single-quote prose arguments: an unescaped backtick inside double quotes triggers shell substitution.
5. Read back the written capsule id with `,ai-kb get <id> --json` and record `stored <id>`, `duplicate of <id>`, or `superseded <old-id> -> <new-id>` in the topic.

MUST NOT persist unverified, transient, or session-only notes; those belong in `,agent-memory note`, not the KB.
Persist only candidates supported by the final evidence; keep unsupported candidates pending in the topic, without a new research or review loop.

## Inline fallback

When delegation is forbidden or unavailable, the root performs the same admission mechanics inline.
Read only the scoped candidate set and relevant topic state; retain compact admitted facts, not capsule dumps.
Follow `~/.agents/skills/k-ai-kb/references/smol-operator.md` and `~/.agents/skills/k-ai-kb/references/cli.md`.
Use deterministic tools; do not invoke another model. Preserve search-first dedupe, metadata, evidence, and readback.
If the CLI or required evidence is unavailable, retain the pending learning in topic history and report that specific gap.
Do not retry failed memory packets automatically or block unrelated delivery on a memory-service outage.

## Memory in a child

A delegated child recalls for itself with `,ai-kb search` / `,ai-kb get` and records session-scoped insights with `,agent-memory note` using the packet's topic and session id; without packet-supplied ids it returns the insight in its terminal artifact instead.
Ordinary children MUST NOT run durable memory writes; only the root persists, with root-verified evidence and `,ai-kb remember`, and no child may invoke another memory agent.
