---
name: jscpd
description: |-
  Detect duplicate (copy-pasted) code blocks across files. Use during any
  refactoring, code cleanup, or DRY improvement — not only when duplicates
  are explicitly mentioned.
---

# jscpd (Copy/Paste Detector)

Use when:

- refactoring or cleaning up code (scan for clones before and after)
- investigating code clones or DRY violations
- generating a duplication report

Do not use:

- unused dependency/export detection: `~/.agents/skills/knip/SKILL.md`
- AI code review: `~/.agents/skills/coderabbit/SKILL.md`

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
4. Re-run to verify duplication dropped.

## Notes

- Supports 150+ languages.
- Non-zero exit when duplication exceeds `--threshold` — useful for CI gates.
- Use `--max-size 1mb` to skip large generated files.
