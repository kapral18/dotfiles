---
sidebar_position: 4
title: Verification
---

# Verification

```bash
uvx pytest scripts/tests/                          # python suite (ralph + isolation + resumability + artifact/control gates + workflows + answer + KB schema/hybrid retrieval/reflector/doc-ingest/curation)
( cd tools/ralph-tui && go test ./... )            # TUI suite (state, cmds, forms, runs, detail, answer, preview, activity, kb, app/view)
AI_KB_HOME="$(mktemp -d)" RALPH_STATE_HOME="$(mktemp -d)" \
  ,ralph go --goal "create $(mktemp -d)/hello.txt with content 'hi'" \
            --workspace "$(mktemp -d)" --subprocess
```

`--runtime local` is deterministic and still exists for `,ralph dry-run` smoke tests; `,ralph go` itself reads runtimes from `roles.json` (Pi rich primary, Cursor Agent secondary).
