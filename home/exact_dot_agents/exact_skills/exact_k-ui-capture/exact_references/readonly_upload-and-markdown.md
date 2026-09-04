# Upload and markdown

## Step 5 — Gated upload and markdown

Load `~/.agents/skills/k-github/references/attachments.md` and follow it end to end:
pre-upload QA, the browser-assisted upload, and the presentation rules for embedding.
Upload only newly captured media; Step 3 supplies the URLs for reused pairs.
Build the proof-mode Claim map before drafting embed text: every behavior claim in the body/comment maps to an inventory item with an adequate asset; drop unmapped claims.
Place `baseline` pairs in the PR/issue body's main Screenshots/Videos section.
Place `intra-change` pairs in a separate comment/thread when requested for reviewer re-verification.
Publish `head-only` proof only in an explicitly approved non-baseline location after the user sees the claim map.
Uploading is a GitHub side effect: show QA summary, claim map, and destination, then confirm explicit approval or a workflow-defined approval packet.
After upload, emit the ready-to-paste markdown block built per those presentation rules.

Completion criterion: new media uploaded and markdown emitted with a complete claim map and a verified publication channel, or local manifest paths returned with upload marked `pending_approval`/`skipped`.
