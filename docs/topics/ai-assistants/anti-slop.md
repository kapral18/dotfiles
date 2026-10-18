# Anti-slop adoption

`k-anti-slop` combines antislop's useful guidance with local extensions through the shared skill tree used by OMP, Codex, and Claude Code.
Its entry point selects nine references: prose, visual design, accessibility, responsive layout, comments, technical documentation, interface copy, data displays, and localization.
The upstream core's purpose test, evidence requirements, and design-direction concepts are folded into those branches.

The adoption is a maintained derivative, not an upstream plugin install or automatic mirror.
It preserves the useful capabilities while adapting workflow and style rules to the existing SOP.
The [skill](../../../home/exact_dot_agents/exact_skills/exact_k-anti-slop/readonly_SKILL.md) and references contain 4,502 whitespace-delimited words, including metadata, against 24,477 across upstream's six skills: about 82% less text with additional categories covered.
These are word counts, not token measurements or evidence of equal model performance.
Only matching references load; this report and the inspection inventory are not part of routine skill loading.
Checks do not prescribe output length: keep already-clear text and add detail only for a concrete gap in meaning or use.
Necessary qualifiers, accessibility requirements, and code contracts still take precedence over brevity.

## Source and inspection boundary

Inspected release **3.2.21**, commit [`439a2ef5b9dd0ebe74e8113ff43f5928d0fe2a6a`](https://github.com/miqdadbadjuber/anti-slop/tree/439a2ef5b9dd0ebe74e8113ff43f5928d0fe2a6a), on 2026-10-18.
The review covered every tracked file: 49 text files and 10 images, 59 total.
The generated core skill has the same body as root `antislop.md`; that identity was checked byte-for-byte after removing frontmatter and surrounding whitespace.
Git history, remote issues, and untracked/generated installer copies are outside this snapshot's inventory.
The retained [MIT notice](../../../home/exact_dot_agents/exact_skills/exact_k-anti-slop/readonly_LICENSE) credits Miqdad Badjuber.

### What upstream actually does

- Six Markdown skills guide a model. The core contains 38 rules, three rule tiers, a design-direction framework, two usage modes, an installation wizard, and a mandatory delivery report. The five supplements require the core and repeat many of its rules as examples and checklists.
- The native manifests expose the same skill directory. Claude's manifest additionally registers a local contrast MCP server through a Node launcher that finds Python. OMP's loader reads that Claude manifest. Codex's manifest exposes skills and interface assets, without MCP registration.
- The npm installer uses Node 18+, `@clack/prompts`, and `picocolors`. It copies selected skills into agent folders. Project installation also writes a marked pointer into entry files such as `CLAUDE.md` or `AGENTS.md`; global installation does not. OMP has a native marketplace route but no row in this installer's agent list.
- `--update` replaces existing antislop skill directories in the current project and home scopes, preserves the selected skill names, and refreshes project pointers. Plugin caches have separate update commands. Its plugin-detection probes cover only four of the seven native plugin routes.
- `--mode` saves a shared preference in `~/.config/antislop/settings.json` on macOS/Linux. Without an explicit session mode or saved choice, the instructions ask during/after and end the turn, even for read-only work. After mode requests an audit file and approval before fixes.
- The only quality calculation is opaque color-pair contrast, implemented twice in Python, once as a CLI and once as a small stdio JSON-RPC MCP server. Neither examines a rendered page. There is no hook enforcing prose quality, design quality, or the mandatory delivery gate; those are model instructions.
- Maintenance scripts synchronize the generated core and installer bundle, generate the guide's pattern index, check 13 repository consistency conditions, and test installation in temporary directories. CI runs on Ubuntu and Windows. It does not benchmark agent output quality.

### Value and verbosity

The strongest material names failures concretely: invented social proof, decorative status indicators, layout chosen before content, unreadable contrast, unreachable controls, broken intermediate widths, and comments that repeat code.
The design framework also guards against removing so much expression that every page becomes bland.
The examples are useful diagnostics, but neither screenshots nor punctuation patterns establish authorship or measured effectiveness.
The comparison images illustrate selected outputs, not a controlled evaluation; the prose example also adds first-person experience not established by its visible prompt.

Upstream's core alone is 9,425 words. UI adds 4,570, copywriting 4,231, accessibility 1,918, responsive layout 2,841, and comments 1,492.
The cost comes from a repeated core prerequisite, Tell/Why/Fix prose, overlapping checklists, installation instructions, and delivery ceremony.
Those mechanisms are separable from the actual quality guidance.

## Distribution choice

Local executable versions inspected: OMP **18.12.1**, Codex CLI **0.163.0**, Claude Code **2.1.301**.
The version commands identify the binaries actually on PATH; a separate pnpm Claude package is not the active mise binary.

| Approach             | What it would add here                                                                            | Decision                                                                                                                  |
| -------------------- | ------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| Native Claude plugin | Six upstream skills, Node/Python MCP launcher, a separate plugin cache and updates                | Keep the capabilities in shared skills; the repeated mode/report rules conflict with the SOP.                             |
| Native OMP plugin    | Marketplace catalog resolves the Claude manifest, including skills and contrast MCP configuration | The installed loader supports this route, but it duplicates guidance already available through shared skills.             |
| Native Codex plugin  | Six skills and plugin identity assets; local `codex plugin --help` confirms the install commands  | It does not supply the same MCP integration as the Claude manifest. A shared script gives all three the same calculation. |
| Shared derivative    | One managed entry point, nine selective references, one local Python calculator                   | Chosen: one reviewed source of truth with existing chezmoi deployment and no separate runtime configuration.              |

Codex reads `$HOME/.agents/skills` directly; see [the official skill locations](https://developers.openai.com/codex/skills/).
Claude's [personal skill location](https://code.claude.com/docs/en/skills) is `~/.claude/skills`, which this repo symlinks to the shared tree.
OMP's installed `src/discovery/builtin.ts` scans `~/.omp/agent/skills`, also symlinked to that tree; `src/discovery/claude-plugins.ts` resolves plugin skills and inline MCP configuration.
Both deployed symlinks resolve to `~/.agents/skills`.
This establishes discovery paths and routing instructions, not a guarantee that every future model invocation follows them.

## Engagement and operation

The [skill catalog](skills.md) advertises `k-anti-slop` for automatic selection.
These existing skills also route to it when the concrete surface is in scope:

| Entry point          | Selected content                                                                                                            |
| -------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| `k-code-quality`     | Prose, documentation, data displays, localization, and code comments; existing web and README routes stay intact.           |
| `k-code-quality-web` | Visual, accessibility, responsive, copy, data displays, or localization references matching the change.                     |
| `k-communication`    | Prose filter, while retaining its own external register and publication rules.                                              |
| `k-readme`           | Prose filter alongside the ReadmeRoast first-use check.                                                                     |
| `k-artifact`         | Matching guidance for authored generated content; cache, feedback, and live-overlay mechanics stay with the artifact skill. |

Direct invocation of `k-anti-slop` also works as a request to apply the filter.
Reciprocal pointers reuse already loaded skills and references for the active invocation.
Prose and visual references conditionally route to the new categories when the requested change touches them.
Creation applies the guidance during work; review-only requests remain read-only. Neither path asks for a separate anti-slop mode.
Start a fresh harness session to ensure the updated skill catalog is discovered.

The [contrast script](../../../home/exact_dot_agents/exact_skills/exact_k-anti-slop/exact_scripts/readonly_contrast.py) needs Python 3.9+ and only its standard library:

```sh
timeout 5 python3 ~/.agents/skills/k-anti-slop/scripts/contrast.py '#777' '#fff'
timeout 5 python3 ~/.agents/skills/k-anti-slop/scripts/contrast.py '#777' '#fff' --minimum 3
```

It accepts three/six-digit RGB hex, with or without `#`, and returns JSON with an unrounded ratio and AA/AAA text and non-text results.
The default minimum is 4.5; 3 and 7 are selectable. Exit 0 means the chosen threshold passes, 1 fails, and 2 rejects invalid input.
It reads no project files and makes no network calls. Resolve transparency, gradients, and image backgrounds before supplying pairs.
A passing pair does not certify the UI's accessibility.

## Capability coverage

Every upstream domain has a local home. Pattern names below group equivalent checks rather than loading the upstream prose at runtime.

| Upstream domain        | Retained capability                                                                                                                                                                                                      | Local reference                                                                                                                                                                                                                               |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Core                   | Purpose and evidence tests; specific audience/action; honest content; design direction; energy, rhythm, motion; scoped create/review completion                                                                          | [Entry point](../../../home/exact_dot_agents/exact_skills/exact_k-anti-slop/readonly_SKILL.md) and [visual](../../../home/exact_dot_agents/exact_skills/exact_k-anti-slop/exact_references/readonly_visual.md)                                |
| UI: visual/color       | Gradients, glass, radius, shadows, glow, backgrounds, dark default, palette, accent concentration, sterile output                                                                                                        | [Visual: decoration](../../../home/exact_dot_agents/exact_skills/exact_k-anti-slop/exact_references/readonly_visual.md)                                                                                                                       |
| UI: layout/components  | Template layouts/cards/bento, spacing, arbitrary steps or tiers, logo bars, unsupported popularity, demo/product distinction, footers, section rhythm                                                                    | [Visual: composition](../../../home/exact_dot_agents/exact_skills/exact_k-anti-slop/exact_references/readonly_visual.md)                                                                                                                      |
| UI: decoration         | Icons/library defaults, emoji, arrows, left stripes, pills, redundant eyebrows, status dots, typography, fake terminals, unrelated illustrations                                                                         | [Visual: decoration](../../../home/exact_dot_agents/exact_skills/exact_k-anti-slop/exact_references/readonly_visual.md)                                                                                                                       |
| UI: flow/apps/motion   | Dead links/controls, filler sections, default dashboard shells, invented stats/feeds/fields, pointless charts, generic tables, unhelpful states, endless loops/stacked animation                                         | [Visual: apps and dashboards](../../../home/exact_dot_agents/exact_skills/exact_k-anti-slop/exact_references/readonly_visual.md)                                                                                                              |
| Copy: tone/voice       | Empty vocabulary, inflated significance, fake social proof, weasel attribution, borrowed authority, chatbot closers, fake candor, signposting, all-caps, actorless passive, anthropomorphism                             | [Prose: substance](../../../home/exact_dot_agents/exact_skills/exact_k-anti-slop/exact_references/readonly_prose.md)                                                                                                                          |
| Copy: rhythm/structure | Forced triples, empty contrasts, aphorisms, staccato drama, synonym cycling, false ranges                                                                                                                                | [Prose: rhythm](../../../home/exact_dot_agents/exact_skills/exact_k-anti-slop/exact_references/readonly_prose.md)                                                                                                                             |
| Copy: evidence/hygiene | Fabricated specifics, gap filling, generic endings, dash/emoji/markdown overuse, excessive quotes, inline-header lists, filler, over-hedging                                                                             | [Prose: fidelity](../../../home/exact_dot_agents/exact_skills/exact_k-anti-slop/exact_references/readonly_prose.md)                                                                                                                           |
| Human                  | Text and non-text contrast, images/gradients, grey pairs, outlines, mouse-only behavior, tab order, focus, color-only feedback, UI states, zoom, onscreen keyboard                                                       | [Accessibility](../../../home/exact_dot_agents/exact_skills/exact_k-anti-slop/exact_references/readonly_accessibility.md) plus [calculator](../../../home/exact_dot_agents/exact_skills/exact_k-anti-slop/exact_scripts/readonly_contrast.py) |
| Mobile                 | Content-driven breakpoints, mobile/intermediate states, fluid sizing, viewport units, padding, grids/stacking, overflow/clipping/children, target size/spacing, hover alternatives, discoverable/fixed/sticky navigation | [Responsive](../../../home/exact_dot_agents/exact_skills/exact_k-anti-slop/exact_references/readonly_responsive.md)                                                                                                                           |
| Code                   | Separators, obvious narration, workflow labels, vague TODOs, signature echo, emoji/end markers, over-explanation, line-by-line narration, stiff/loud wording; preserve meaningful contracts                              | [Comments](../../../home/exact_dot_agents/exact_skills/exact_k-anti-slop/exact_references/readonly_comments.md)                                                                                                                               |

### All 38 core rules

| Rules                                                                                   | Adoption                                                                                                                                             |
| --------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| R-01 gradients; R-04 icons; R-06 typography; R-07 backgrounds; R-08 arrows; R-09 badges | Visual reference: judge purpose, readability, and existing direction; no categorical style ban.                                                      |
| R-02 em dashes; R-16 buzzwords                                                          | Prose reference: diagnose filler in context; preserve quotations, technical meaning, and explicit voice.                                             |
| R-03 mobile                                                                             | Responsive and accessibility references: reflow, overflow, targets, keyboard, and intermediate widths.                                               |
| R-05 rhythm; R-14 cards; R-20 identity                                                  | Visual composition follows content, with intentional hierarchy and direction.                                                                        |
| R-10 glass; R-11 radius; R-12 shadow; R-13 glow                                         | Visual reference preserves useful emphasis without arbitrary fixed dose limits.                                                                      |
| R-15 CTAs                                                                               | Prose and visual references tie labels to actual actions and availability.                                                                           |
| R-17 numbers; R-18 testimonials; R-36 claims; R-38 content                              | Entry point forbids invented evidence; prose and visual references apply that boundary to their concrete surfaces.                                   |
| R-19 motion                                                                             | Visual reference retains purposeful motion and reduced-motion behavior.                                                                              |
| R-21 dark mode; R-34 themes                                                             | Preserve intended appearance and check every supported theme; no automatic theme-toggle feature.                                                     |
| R-22 imagery; R-30 clones                                                               | Preserve requested identity and meaningful assets; explicit direction governs use of a reference design. Unrequested redesign remains outside scope. |
| R-23 user permission                                                                    | Existing SOP owns decisions and authorization. Evidence-backed, reversible choices proceed without an extra permission cycle.                        |
| R-24 navigation; R-26 controls; R-27 states; R-28 FAQ                                   | Visual/accessibility references require truthful destinations, real actions, reachable states, and relevant content.                                 |
| R-25 contrast                                                                           | Corrected standards guidance and one strict local calculator; no rounded threshold comparisons.                                                      |
| R-29 palette; R-31 design rationale; R-37 direction                                     | Visual reference retains deliberate choices and the three design qualities; no mandatory design file or rationale for every decorative choice.       |
| R-32 keyboard                                                                           | Accessibility reference uses the control's native semantics and valid managed-focus patterns.                                                        |
| R-33 editing method                                                                     | Existing edit-scope and tool rules remain authoritative; no blanket ban on legitimate patch tools.                                                   |
| R-35 build/run/click                                                                    | Existing bounded static/local verification and user-requested live checks replace mandatory click-through sessions.                                  |

The five craftsmanship principles map to direction, real behavior, actual content, reachable states, and evidence in these references.
The mandatory delivery table is replaced by the existing completion and review workflow; the quality checks it repeated remain in the relevant branches.

### Corrections and deliberate adaptations

- Upstream labels 18px text “large.” [WCAG uses 18pt regular or 14pt bold](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html). The derivative also uses the current sRGB breakpoint, 0.04045; the older 0.03928 constant does not change results for the accepted 8-bit inputs.
- The mobile 44px target is retained as a usability aim, with the [24px WCAG 2.2 AA minimum and exceptions](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html) identified correctly.
- Valid managed focus can require negative `tabindex`; keyboard keys depend on the widget. The derivative avoids blanket removal or uniform key requirements.
- Comments can need more than two lines. Preserve license notices, tooling directives, API contracts, removal conditions, and useful issue history; shortening them is not an end in itself.
- The prose examples are not copied as rewrite recipes: stronger wording must not introduce unsupported facts or personal experience.
- Absolute vocabulary/punctuation bans, decorative dose caps, mandatory theme toggles, and compulsory design-document creation are replaced by purpose, user direction, and requested scope.
- Installer/wizard prompts, saved modes, plugin caches, audit-file numbering, and the MCP transport are omitted. Chezmoi, the SOP, scoped reviews, and the shared calculator cover their useful roles with one implementation.
- Branding assets, community policy, release-history prose, and distribution-specific maintenance code stay upstream. They are inspected evidence, not runtime capabilities needed by the shared skill.

## Local extensions

Upstream coverage is a foundation, not a limit on the maintained skill.
The following additions address decisions the original references did not cover concretely.
They supplement the base checks; they do not replace the existing prose, visual, accessibility, responsive, or comment guidance.

| Category                | Gap in the base guidance                                                                                                                                              | Added reference and consumer                                                                                                                                                                                              |
| ----------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Technical documentation | Accurate prose alone does not establish a reproducible procedure, a copyable example, or the meaning of absent/null/default values.                                   | [Documentation](../../../home/exact_dot_agents/exact_skills/exact_k-anti-slop/exact_references/readonly_documentation.md), selected for human task guides, API/CLI docs, and examples, including relevant README changes. |
| Interface copy          | Generic helpful-state guidance does not distinguish a field error from a service failure, or a queued action from completed work.                                     | [Interface copy](../../../home/exact_dot_agents/exact_skills/exact_k-anti-slop/exact_references/readonly_interface_copy.md), selected for labels, validation, confirmations, and status messages.                         |
| Data displays           | Naming real metrics and readable labels does not prevent misleading scales, mismatched denominators, missing-data substitution, or unsupported benchmark conclusions. | [Data visualization](../../../home/exact_dot_agents/exact_skills/exact_k-anti-slop/exact_references/readonly_data_visualization.md), selected for charts, quantitative tables, metrics, and benchmarks in UI or reports.  |
| Localization            | Responsive English text does not establish valid translated messages, plural handling, locale formatting, or bidirectional presentation.                              | [Localization](../../../home/exact_dot_agents/exact_skills/exact_k-anti-slop/exact_references/readonly_localization.md), selected for translation, locale-sensitive behavior, and supported multilingual content.         |

### Evidence and boundaries

Primary guidance inspected on 2026-10-18 supports these decisions. The short excerpts anchor the specific claims; the references are scoped local guidance, not copies of those manuals.

| Decision                               | Primary source and supporting passage                                                                                                                                                           | Boundary                                                                                            |
| -------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| Give readers the action's context.     | [Google procedures](https://developers.google.com/style/procedures): “Tell the reader where to complete an action”                                                                              | Preserve project conventions rather than importing Google's complete formatting style.              |
| Identify incomplete examples.          | [Google code samples](https://developers.google.com/style/code-samples): “Indicate omitted code by using a comment”                                                                             | Excerpts remain valid when visibly identified; not every example must become a standalone program.  |
| Make validation recovery actionable.   | [GOV.UK error messages](https://design-system.service.gov.uk/components/error-message/): “explain what went wrong and how to fix it.”                                                           | Service failures need a truthful service-level explanation, not a fictitious field correction.      |
| Preserve proportional bar comparisons. | [Government Analysis Function charts](https://analysisfunction.civilservice.gov.uk/policy-store/data-visualisation-charts/): “breaking the numerical axis distorts these relative proportions.” | Range bars and line/scatter plots encode different relationships; the reference distinguishes them. |
| Match language metadata to content.    | [W3C internationalization](https://www.w3.org/International/quicktips/): “Declare the language of documents and indicate internal language changes.”                                            | Apply within supported locales; do not add an unrequested language or locale switcher.              |
| Translate messages as units.           | [ICU message formatting](https://unicode-org.github.io/icu/userguide/format_parse/messages/): “a message has to be written and translated as a single unit”                                     | Reuse the existing formatter and preserve program placeholders; no framework migration is implied.  |

Source-research mechanics stay with `k-public-sources`; architecture stays with `k-codebase-design`; implementation and test design stay with `k-code-quality` and `k-code-quality-tests`.
AI-facing instruction craft stays with `k-writing-great-skills` and `k-instruction-boundaries`.
Those concerns already have explicit owners; duplicating them here would add conflicting rules and loading cost.

### Routing and preservation checks

| Requested change                       | Applicable additional guidance            | Boundary to retain                                                                      |
| -------------------------------------- | ----------------------------------------- | --------------------------------------------------------------------------------------- |
| Correct a README spelling error        | None solely because it is a README        | Keep the existing prose/ReadmeRoast route and narrow edit scope.                        |
| Repair a README installation example   | Documentation                             | Check setup, command, and result; do not rewrite unrelated sections.                    |
| Rewrite a product validation error     | Interface copy                            | Match the actual failure and recovery; do not claim a copy edit fixes backend behavior. |
| Compare benchmark results in a report  | Data visualization                        | Preserve measurement context and uncertainty even when no browser UI is involved.       |
| Translate a pluralized error message   | Interface copy and localization           | Preserve message variables, meaning, and supported locale scope.                        |
| Change a comment or contrast threshold | None solely because categories were added | Preserve the original comment rules and contrast calculation.                           |
| Read a live-page overlay               | No generated-content route                | Keep the overlay's existing read-only/permission boundary.                              |

The entry point selects by the requested change and reuses existing loads; the new references are not an always-on bundle.
Static checks establish that references exist, routes cover these scenarios, original rules remain, and deployed files match.
They do not measure live model adherence, language quality, or comparative effectiveness.
Future additions need a concrete uncovered decision, an actual consumer, a precise trigger, and a check against the existing owners before they earn another reference.

## Complete tracked-file inventory

All paths below are relative to the pinned upstream root. Text was read in full; every image was viewed.

| Path                                       | Role inspected                                                                      |
| ------------------------------------------ | ----------------------------------------------------------------------------------- |
| `.agents/plugins/marketplace.json`         | Codex local marketplace entry and installation policy                               |
| `.claude-plugin/contrast-mcp-launcher.mjs` | Node launcher, Python detection, stdio forwarding                                   |
| `.claude-plugin/marketplace.json`          | Claude marketplace catalog                                                          |
| `.claude-plugin/plugin.json`               | Skills and contrast MCP registration                                                |
| `.cline-plugin/plugin.js`                  | No-op plugin entry; no hooks or tools                                               |
| `.codex-plugin/plugin.json`                | Skills path and interface assets                                                    |
| `.cursor-plugin/marketplace.json`          | Cursor marketplace catalog                                                          |
| `.cursor-plugin/plugin.json`               | Skills and always-applied rule directory                                            |
| `.github/ISSUE_TEMPLATE/bug_report.yml`    | Reproduction fields and platform/version context                                    |
| `.github/ISSUE_TEMPLATE/config.yml`        | Guide, contribution, and security links                                             |
| `.github/ISSUE_TEMPLATE/rule_gap.yml`      | Rule-gap evidence template                                                          |
| `.github/PULL_REQUEST_TEMPLATE.md`         | Release and check requirements                                                      |
| `.github/workflows/ci.yml`                 | Ubuntu/Windows consistency and installer checks                                     |
| `.gitignore`                               | Local agent, build, and Python exclusions                                           |
| `.kimi-plugin/plugin.json`                 | Skills and system-prompt pointer                                                    |
| `.omp-plugin/marketplace.json`             | OMP catalog; manifest comes from Claude directory                                   |
| `CODE_OF_CONDUCT.md`                       | Contributor Covenant and enforcement policy                                         |
| `CONTRIBUTING.md`                          | Version synchronization, generated files, review expectations                       |
| `GUIDE.md`                                 | All eleven installation routes, updates, removal, generated pattern index, caveats  |
| `LICENSE`                                  | MIT permission and retained copyright                                               |
| `README.md`                                | Product claims, installation entry points, comparative illustrations                |
| `ROADMAP.md`                               | Release history and deferred compact edition                                        |
| `SECURITY.md`                              | Entry-file writes, local scripts, and design-document data boundary                 |
| `antislop.md`                              | Canonical core; generated skill body matches                                        |
| `assets/antislop-banner.png`               | Product banner                                                                      |
| `assets/compare/code/after.webp`           | Reduced-comment example                                                             |
| `assets/compare/code/before.webp`          | Comment-heavy example                                                               |
| `assets/compare/text/after.webp`           | Shorter announcement with placeholders and added experience claim                   |
| `assets/compare/text/before.webp`          | Promotional announcement example                                                    |
| `assets/compare/ui/w-all.webp`             | Filter plus supplied design illustration                                            |
| `assets/compare/ui/w-antislop.webp`        | Filter-only illustration                                                            |
| `assets/compare/ui/w-design.webp`          | Design-only illustration with invented metrics                                      |
| `assets/compare/ui/without.webp`           | Generic UI example                                                                  |
| `assets/profile.png`                       | Plugin identity image                                                               |
| `cli/.gitignore`                           | Dependency and bundled-skill exclusions                                             |
| `cli/index.mjs`                            | Interactive selection, overwrite confirmation, update/mode/version paths            |
| `cli/lib/banner.mjs`                       | Installer identity/version output                                                   |
| `cli/lib/install.mjs`                      | Agent targets, copies, duplicate detection, plugin probes, pointer scanner, updates |
| `cli/lib/settings.mjs`                     | Mode path resolution, persistence, validation                                       |
| `cli/package-lock.json`                    | Pinned dependency graph                                                             |
| `cli/package.json`                         | npm binary, dependencies, packaging scripts                                         |
| `cli/scripts/smoke-test.mjs`               | Temporary-project runner, CLI guard checks, cleanup                                 |
| `cli/scripts/smoke-worker.mjs`             | Settings, paths, conflicts, pointer preservation, mixed installs, updates           |
| `cli/scripts/sync-skills.mjs`              | Core generation and installer bundle copying                                        |
| `package.json`                             | Pi/Cline package metadata                                                           |
| `plugin.json`                              | Minimal root plugin identity                                                        |
| `rules/antislop.md`                        | Always-on pointer and mode instructions                                             |
| `rules/antislop.mdc`                       | Cursor always-apply pointer                                                         |
| `scripts/check-repo.mjs`                   | Thirteen structural/document consistency checks                                     |
| `scripts/skill-index.mjs`                  | Generated guide catalog from skill headings                                         |
| `skills/antislop-code/SKILL.md`            | Comment diagnostics and preservation boundaries                                     |
| `skills/antislop-copywriting/SKILL.md`     | Prose diagnostics and rewrite examples                                              |
| `skills/antislop-human/SKILL.md`           | Accessibility checks and contrast table                                             |
| `skills/antislop-human/contrast-check.py`  | CLI calculation, exit codes, table self-test                                        |
| `skills/antislop-human/contrast-mcp.py`    | Duplicate calculation in stdio MCP transport                                        |
| `skills/antislop-layoutmobile/SKILL.md`    | Responsive-layout patterns                                                          |
| `skills/antislop-ui/SKILL.md`              | Visual, app, composition, and motion patterns                                       |
| `skills/antislop/SKILL.md`                 | Generated core with skill frontmatter                                               |
| `skills/antislop/VERSION`                  | Installed-version stamp                                                             |

## Maintenance and verification

Edit the chezmoi sources linked below, then apply only the affected skill targets.
There is no upstream auto-update: inspect a later pinned revision and reconcile changes against the coverage table before adopting them.
Keep attribution when adapting substantial material.

`scripts/check.py` maps the calculator directory to `scripts/tests/test_anti_slop_contrast.py`.
Tests exercise known extreme ratios, both sides of 3/4.5/7 thresholds, the upstream rounding regression, independent AA/AAA results, short/mixed-case hex, and invalid input.
The positive tests were observed failing before the calculator existed. `make check` supplies affected formatting, docs navigation, reference-size gates, and tests.
Skill routing and deployment are checked from source and resolved paths. Live model effectiveness is not measured by those checks.
