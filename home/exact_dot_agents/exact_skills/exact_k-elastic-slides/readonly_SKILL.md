---
name: k-elastic-slides
description: "Manual-only workflow for generating, updating, or styling Elastic-themed Google Slides by presentation URL or slide ID."
disable-model-invocation: true
---

# Elastic Google Slides

Manual-only overlay for Elastic-themed Google Slides decks.
Use it when the user explicitly asks for Elastic slide generation, deck styling, ownership slides, Kibana plugin/package slides, or Elastic visual polish.

This skill owns Elastic domain content and style.
Generic Google Workspace mechanics stay with `k-google-workspace`; generic Slides geometry and `gws` batchUpdate patterns stay in `k-google-workspace/references/slides-deck-design-and-automation.md`.

## Load Order

1. Load `~/.agents/skills/k-google-workspace/SKILL.md`.
2. Load `~/.agents/skills/k-google-workspace/references/slides-deck-design-and-automation.md`.
3. Use this skill for Elastic-specific content, palette, ownership, and deck conventions.
4. Load `references/templates.md` only when you need executable Elastic batchUpdate snippets.

Done when the target deck, slide IDs, intended operation, source content, and verification method are all explicit.

## Input Packet

Extract or ask for:

- Target presentation URL or `presentationId`.
- Target `slideId` when updating an existing slide.
- Operation: `generate`, `update`, or `format`.
- Slide type: showcase, architecture grid, agenda/overview, ownership map, or cleanup pass.
- Source content: user-provided text, local repo paths, screenshots, or manifest discovery request.

If the prompt includes a Slides URL, parse `presentationId` from `/d/<id>/` and `slideId` from `#slide=id.<id>`.
Read the current presentation with `gws` before planning mutations.

## Elastic Content Rules

Use Elastic-specific rules only when the deck content asks for Elastic, Kibana, plugin, package, team, or ownership material.

- Source Kibana plugin/package metadata from live local files such as `kibana.jsonc`.
  Search exact paths under `src/platform/plugins/`, `x-pack/platform/plugins/`, `src/platform/packages/`, and `x-pack/platform/packages/`.
- Treat co-owned components as owned for deck purposes.
  Include them and label shared responsibility explicitly, for example `Co-owned: Data Discovery`, `Co-owned w/ AppEx`, or `Co-owned w/ Core`.
- Link each plugin or package title to its canonical GitHub source path: `https://github.com/elastic/kibana/blob/main/<relative_path_to_kibana.jsonc>`.
- Keep lower taglines and banner boxes only when they add new information.
  Give cards and descriptions enough vertical room before adding decorative containers.

When source truth is unavailable locally, mark that content `Unknown` and use user-provided copy instead of inventing ownership or status.

## Elastic Visual System

Use these tokens unless the existing deck has a stronger local theme:

| Token             | Role                                      | Hex / RGB                               |
| ----------------- | ----------------------------------------- | --------------------------------------- |
| Elastic Blue      | Slide titles, hyperlinks, primary accents | `#005FB8` (`r: 0.0, g: 0.37, b: 0.72`)  |
| Sapphire Blue     | Card or section headers                   | `#005FB8` / `#1d4ed8`                   |
| Slate Grey        | Subtitles and metadata lines              | `#4a5568` (`r: 0.29, g: 0.33, b: 0.41`) |
| Charcoal          | Body and bullet text                      | `#24292f` (`r: 0.14, g: 0.16, b: 0.18`) |
| Card Background   | Soft card fill                            | `#f8fafc` (`r: 0.97, g: 0.98, b: 0.99`) |
| Card Border       | Subtle card outline                       | `#d0d7de` (`r: 0.82, g: 0.84, b: 0.87`) |
| Offering Badge    | Serverless / ECH / Self-Managed pill      | `#e0f2fe` (`r: 0.88, g: 0.95, b: 0.99`) |
| Active Badge      | Active development pill                   | `#ecfdf5` (`r: 0.92, g: 0.99, b: 0.96`) |
| Maintenance Badge | Maintenance-only pill                     | `#fef3c7` (`r: 1.00, g: 0.95, b: 0.78`) |

Typography follows the generic Slides reference.
Elastic-specific defaults are blue titles/headers, slate italic metadata, charcoal body text, and small rounded status badges.

## Slide Patterns

Use the generic layout templates, then apply Elastic content:

- **2-column showcase**: left column for narrative, badges, links, or ownership notes; right media box for screenshots or UI diagrams.
- **3-card architecture grid**: one card per subsystem, ownership group, package family, or workflow stage.
- **Overview / agenda**: section cards with short labels and one evidence-backed sentence per section.

Keep each slide to one main claim. Move overflow into speaker notes or a follow-up slide.

## Execution Loop

1. Read the deck with `gws slides presentations get`.
2. Resolve source content: local manifests, user copy, images, or screenshots.
3. Build a small batchUpdate request with stable object IDs of at least 5 characters.
4. Apply atomic text updates: `deleteText`, `insertText`, `updateTextStyle`, then `updateParagraphStyle`.
5. Apply hyperlinks to plugin/package names and titles.
6. Re-read the deck and verify expected objects, text, links, and transforms.
7. Use browser visual QA for rendered spacing, overflow, badge wrapping, and image margins.

For new batch scripts, start from `references/templates.md` and keep one script per target slide or cohesive deck operation.

## Done Criteria

Return:

- Presentation ID and affected slide IDs.
- Source evidence used for Elastic content.
- Objects changed or created.
- Visual QA result and any remaining layout risk.
- Compatibility impact from the active task.
