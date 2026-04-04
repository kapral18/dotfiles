---
name: google-workspace
description: Inspect or change Gmail / Drive / Calendar / Admin / Docs / Sheets and other Google Workspace data via gws CLI.
tool_version: gws 0.18.1
---

# Google Workspace (`gws`) Skill

Use this skill when the user asks to inspect or change Google Workspace resources, including:

- Gmail
- Drive
- Calendar
- Docs / Sheets / Slides / Forms
- Admin Reports
- People / Chat / Tasks / Keep / Meet / Classroom
- other Google Workspace surfaces exposed by `gws`

Default interface:

- Use `gws` for Google Workspace activity.
- Verify the local CLI first: `command -v gws`, `gws --version`, `gws --help`.
- Before using a method in-session, inspect it with `gws schema <service.resource.method>`.
- Then use direct `gws <service> <resource> [sub-resource] <method>` commands.
- Do not invent service/resource/method names, params, request bodies, or scopes; verify them from `gws schema` output.

When NOT to use:

- GitHub activity: `~/.agents/skills/github/SKILL.md`
- Local git activity: `~/.agents/skills/git/SKILL.md`
- Browser automation for a Google Workspace task that `gws` already supports
- Unsupported Google products or UI-only flows that `gws` cannot perform (in that case, say `gws` does not cover the task and ask before switching tools)

External truth rules:

- Treat auth, scopes, service availability, and response shape as unknown until verified.
- If a `gws` call fails, inspect `gws schema ...` and report the exact auth / scope / parameter error instead of guessing.
- Prefer the smallest safe probe that proves the next step.

Execution loop:

1. Identify the exact account and target object.
2. Inspect the method with `gws schema ...`.
3. Read current state first with the smallest relevant `list` / `get` call.
4. Perform the requested mutation with `gws`.
5. Re-read state to verify the result.

Targeting & safety:

- Prefer explicit identifiers from live reads (IDs, email addresses, file IDs, event IDs, label IDs).
- For Gmail user-scoped calls, prefer `{"userId":"me"}` unless the user explicitly wants a different mailbox.
- Before destructive actions (delete/remove/trash/send), enumerate the exact targets first.
- If the user asks to remove a set of items, operate on the enumerated IDs you just verified; do not guess or pattern-match blindly.
- Do not fall back to manual HTTP requests when `gws` supports the task.

Output guidance:

- Default to JSON unless the user asked for another format.
- Use `--page-all` only when the user wants the full result set and the volume is manageable.
- Summarize the exact objects changed and the verification result.

Examples:

```bash
gws schema gmail.users.settings.filters.list
gws gmail users settings filters list --params '{"userId":"me"}'

gws schema drive.files.list
gws drive files list --params '{"pageSize":10}'
```
