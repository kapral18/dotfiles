---
name: knip
description: "Use when finding unused JS/TS files, dependencies, exports, package.json entries, or missing/unlisted dependencies with knip."
tool_version: knip 5.88.0
---

# Knip (Dead Code & Dependency Cleanup)

Do not use:

- copy/paste detection: `~/.agents/skills/jscpd/SKILL.md`

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

1. Run `npx knip`.
2. Address configuration hints (adjust `knip.json`) until a re-run of `npx knip` reports no new configuration hints and no previously-seen false positive reappears.
3. Fix reported issues in priority order:
   - unused files (removes the most noise)
   - unused dependencies / devDependencies
   - unused exports
4. Re-run after each batch — removing files often exposes new unused exports.

## Confidence rules

Auto-delete: orphaned files, unused deps, internal unused exports, unused type exports.

Ask first: anything in `src/index` / `lib/` / public API paths, deps that may be CLI-only or peer deps, dynamically imported files.

## Notes

- Knip finds unused files/deps/exports across the project. It does NOT find unused imports/variables inside a file — that is a linter's job.
- Supports monorepos, all major package managers, and 100+ framework plugins (auto-detected).
