# Spec Packet Template

The template used by `~/.agents/skills/k-spec/SKILL.md` and written to `/tmp/specs/<pwd>/<topic>.spec.md`.
Keep every section and every criterion's `check:`/`judgment:` tag; omit `External dependencies` only when there are none.

```markdown
# Spec packet: <topic>

Goal: <one sentence — what exists after, that does not exist now>
Context: <why now; links: issue/PR/thread/prototype verdict>

Semantic delta: <none | old rule; new rule; intended differences; preserved differences; evidence>

In scope:

- <...>

Out of scope (binding for /k-build):

- <...>

Acceptance criteria:

1. <observable statement>
   check: `<command>`            # run from repo root; pass = exit 0
   now: planned                # execute once in the final Verify stage
2. <observable statement>
   judgment: <what evidence settles it>

Risks / unknowns:

- <risk + probe> | Unknown because <reason>

External dependencies (omit section when none; consumers must not start blocked criteria):

- <decision/sign-off needed> — owner: <who>; blocks: criterion <N>; recommended default: <what to assume if forced>

Compatibility intent: none | removes existing behavior (requested) | preserves existing behavior (requested)
```
