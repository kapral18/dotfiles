---
sidebar_position: 4
title: Verification
---

# Verification

```bash
uvx pytest scripts/test_ralph.py scripts/test_ai_kb.py scripts/tests/  # ralph suite (workflows/resumability/isolation/criteria checks) + KB suite + shared harness tests
( cd tools/ralph-tui && go test ./... )            # TUI suite (state, cmds, forms, runs, detail, answer, preview, activity, kb, app/view)
AI_KB_HOME="$(mktemp -d)" RALPH_STATE_HOME="$(mktemp -d)" \
  ,ralph go --goal "create $(mktemp -d)/hello.txt with content 'hi'" \
            --workspace "$(mktemp -d)" --subprocess
```

`,ralph dry-run` is deterministic by construction: it only assembles and prints the planner prompt (`--goal`/`--memory-query`/`--memory-limit`/`--acceptance`) without invoking any harness, so there is no `--runtime` flag to set. `,ralph go` itself reads runtimes from `roles.json` (cursor-first defaults — see [Roles and diversity](roles-and-diversity.md); pi remains fully supported for non-cursor providers).
