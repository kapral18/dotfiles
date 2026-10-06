---
name: k-ai-kb
description: "Use to search past-session knowledge with ,ai-kb before working on a subsystem or unfamiliar error, or to store a verified reusable gotcha or recipe."
---

# Durable Knowledge (`,ai-kb`)

`,ai-kb` is an on-demand local knowledge base of short capsules. Nothing injects it automatically; you search and write it yourself.
Task progress does not belong here: use `,handoff` (`k-handoff`) for that.
The CLI contract is `~/.agents/skills/k-ai-kb/references/cli.md`; `,ai-kb <command> --help` wins on conflict.

## Search

Search when you start on a subsystem you may have worked on before, or when you hit an unfamiliar error:

```bash
,ai-kb search "<literal identifiers or error text>" --limit 5 --json
```

Use exact symbols, paths, flags, and error strings; paraphrase matches poorly.
Treat hits as leads. Verify a hit against the live repo or tool before relying on it.

## Remember

Write only an insight that is verified in this session, reusable beyond this task, and specific.
Not progress notes, guesses, or session state.

1. Search first with the insight's literal identifiers.
   A stale or wrong capsule on the same point: pass `--supersedes <its-id>` (amends it in place). A duplicate: stop.
2. Set every metadata field deliberately: honest `--kind`, reuse-breadth `--scope` (`--workspace` only for workspace/project), the evidence anchor as `--source`, honest `--confidence`, `--domain` tags.
   A degraded-metadata warning means fix the field, not ignore it.
3. Front-load literal identifiers in title and body.
4. Single-quote prose arguments; an unescaped backtick inside double quotes triggers shell substitution.
5. Read back with `,ai-kb get <id> --json`.

Write at most a few capsules per session, at the end, after the work is verified.
