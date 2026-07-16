---
name: k-jscpd
description: "Use when detecting duplicated code during refactors, cleanup, DRY work, clone investigation, or duplication reporting with jscpd."
tool_version: jscpd 4.0.8
---

# jscpd (Copy/Paste Detector)

Do not use:

- unused dependency/export detection: `~/.agents/skills/k-knip/SKILL.md`

First actions:

1. `command -v jscpd` — abort with install instructions if missing.
2. Determine scope: which directories or glob patterns to scan.
3. Run the scan and report findings.

## Commands

```bash
jscpd ./src                                     # scan a directory
jscpd ./src --min-lines 10 --min-tokens 70      # raise thresholds
jscpd ./src --mode strict                       # exact token match
jscpd ./src --mode mild                         # catches renamed clones
jscpd ./src --format javascript,typescript      # limit to specific langs
jscpd ./src --ignore "**/test/**,**/dist/**"    # exclude patterns
jscpd ./src --reporters console,html --output ./report  # HTML report
jscpd ./src --threshold 5                       # fail if >5% duplication
```

## Workflow

1. Run `jscpd` on the target directory.
2. Review reported clones — each shows both locations and the duplicated block.
3. Refactor: extract shared logic into a common module or utility.
4. Re-run and confirm the duplication % or clone count is strictly lower than the pre-refactor baseline (or that `--threshold` now passes if one is set).

## Notes

- Supports 150+ languages.
- Non-zero exit when duplication exceeds `--threshold` — useful for CI gates.
- Use `--max-size 1mb` to skip large generated files.
