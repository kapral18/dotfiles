---
name: k-knip
description: "Use when finding unused JS/TS files, deps, exports, package entries, or missing/unlisted deps with knip."
tool_version: knip 5.88.0
---

# Knip (Dead Code & Dependency Cleanup)

Subagent dispatch: inline (mechanical for a settled full scan and report) — small scans run directly; cleanup goes through Produce.

Do not use:

- copy/paste detection: `~/.agents/skills/k-jscpd/SKILL.md`

First actions:

1. `command -v knip` or verify `npx knip --version` works.
2. Run `npx knip` and read **configuration hints first** (top of output) — fix config before acting on reported issues.
3. If a `knip.json` / `knip.jsonc` exists, review it; otherwise knip works zero-config.

## Commands

```bash
npx knip                          # full analysis
npx knip --production             # production files only (skip tests/config)
npx knip --fix                    # auto-remove unused deps and exports
npx knip --fix --allow-remove-files  # also delete unused files
npx knip --reporter json          # machine-readable output
```

## Workflow

For find/check/report requests, inspect configuration hints and report findings or required config corrections;
do not edit configuration or code. Run the cleanup steps below only when the user asked for cleanup/removal.

1. Run `npx knip`.
2. For authorized cleanup, resolve configuration hints from source and include configuration changes in the production batch;
   do not iterate the scanner to green.
3. Fix reported issues in priority order:
   - unused files (removes the most noise)
   - unused dependencies / devDependencies
   - unused exports
4. Run the integrated cleanup scan once in final Verify.
   Report remaining/newly exposed issues without automatically opening another cleanup batch.

## Confidence rules

Auto-delete (only when the user asked for cleanup/removal): orphaned files, unused deps, internal unused exports, unused type exports.
For a find, check, or report invocation, report the hits and delete nothing.

Ask first: anything in `src/index` / `lib/` / public API paths, deps that may be CLI-only or peer deps, dynamically imported files.

## Notes

- Knip finds unused files/deps/exports across the project. It does NOT find unused imports/variables inside a file — that is a linter's job.
- Supports monorepos, all major package managers, and 100+ framework plugins (auto-detected).

## Root moves

Only the active root/main session follows this section; a delegated leaf skips it and returns findings to its parent.
Launch one mechanical packet for a settled full scan and report with a stated rule and return;
the root MUST NOT substitute its own inline scan for that packet absent an explicit user no-delegation instruction;
if the lane is unavailable report blocked. Small scans stay inline; cleanup goes through Produce.
