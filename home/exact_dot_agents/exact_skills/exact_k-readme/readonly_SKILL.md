---
name: k-readme
description: "Use when creating, editing, or reviewing README files; apply ReadmeRoast checks to the project's actual audience and scope."
tool_version: readmeroast 1.0.0
---

# README Writing

Use [ReadmeRoast](https://github.com/princejain756/readmeroast) as an advisory check on the README's first-use experience.
The score measures conventions, not factual accuracy or writing quality.
Load `~/.agents/skills/k-anti-slop/SKILL.md` and its prose reference for wording; reuse them if already loaded for this invocation.

## Workflow

1. Read the target README and the project's manifests, entry points, docs, and license as needed to verify its claims.
   Identify the audience and requested edit scope before drafting.
   A package, internal component, and curated list need different introductions.
2. Write or edit within that scope using the rubric below. Keep working examples, prerequisites, and limitations accurate.
   Do not invent install commands, features, screenshots, results, or a license to satisfy a check.
3. After the draft, run the local check below once per changed README. For review-only requests, check the existing file without editing it.
   Resolve each finding against the source: fix supported issues within scope;
   explain false positives, inapplicable checks, and out-of-scope gaps.
   Rerun only after an affected edit. A narrow README correction does not authorize a whole-file rewrite.
4. Finish when the requested change is complete and every finding is accounted for.
   Report the score only if the CLI produced it, with material limitations or accepted exceptions.
   Never chase 100/100 by adding filler or hiding real limitations.

## Local check

Use the installed `readmeroast` binary (`command -v readmeroast`). Dotfiles manage it through the global pnpm list.
If unavailable, apply the rubric manually and report that the CLI check was unavailable; do not fetch a package during verification.

Set `readme_path` to the intended file's resolved absolute path, then run:

```sh
readme_path='/absolute/path/to/README.md'
test -f "$readme_path" && timeout 15 readmeroast "$readme_path" --json
```

The file guard is required: a missing local path can be interpreted as `owner/repo` and fetch GitHub.
If the guard fails, locate the intended README before proceeding. Do not pass a GitHub URL or repository slug for local writing work.
Read `checks` and `findings[].fix` from the JSON; use constructive findings, not `roast` text.
An error or timeout is not a score; use the manual rubric and report the failed check.

## Rubric

Apply every row in context; mark inapplicable checks instead of adding unnecessary sections.

| Check              | Points | Writing decision                                                                                                                       |
| ------------------ | ------ | -------------------------------------------------------------------------------------------------------------------------------------- |
| Pitch              | 15     | Say what the project does and who it serves near the title, before badges and detail.                                                  |
| Install            | 15     | For installable software, give the real command and prerequisites under a findable heading.                                            |
| Usage              | 15     | Show the common first task with a concrete example and its expected result.                                                            |
| Language tags      | 8      | Tag fenced code with its language; use `text` for plain output.                                                                        |
| Screenshot or demo | 10     | Use a real visual or output example when it helps explain the product; a library or internal README may not need an image.             |
| License            | 8      | Link or name the project's actual license when established. Flag missing licensing information; never select one on the user's behalf. |
| Length             | 6      | Keep the entry point useful and move deep reference material to docs. The scorer's 150–6000-word band is not a length requirement.     |
| Relative links     | 9      | Check local links and images against their intended targets, including heading fragments.                                              |
| Prose              | 10     | Replace vague promotion and repetitive decoration with concrete facts. Vocabulary and punctuation are not proof of AI authorship.      |
| Stale promises     | 4      | Remove obsolete placeholders or describe current status accurately; preserve real limitations and relevant roadmap information.        |

## Tool limits

- ReadmeRoast uses regex heuristics.
  A badge can satisfy its image check, and an unrelated code block can satisfy its usage check;
  inspect whether they actually help the reader.
- Local link checks cover some inline relative paths.
  They skip external URLs and heading anchors, miss reference-style links, and can misread encoded paths, HTML, or code examples.
  Verify disputed findings against the files and Markdown before editing.
- Root-relative paths in local mode resolve from the README's directory, which can disagree with repository-root links in nested READMEs.
- The CLI does not execute examples or verify install commands. Confirm those from project source; a passing score proves neither works.

CLI and scoring rules inspected at [upstream commit 528a840](https://github.com/princejain756/readmeroast/tree/528a8407c748601411dca0f3e8ad33df4d4e0b80/src).
Version comes from installed package metadata: this release has no version flag.
