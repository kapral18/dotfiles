---
name: k-buildkite
description: "Use when checking Elastic Buildkite status, triggers, logs, CI failures, or any buildkite.com URL via bk."
tool_version: bk 3.32.2
allowed-tools: Bash(bk:*)
---

# Buildkite — CI/CD

## URL Intercept (Mandatory)

Buildkite URLs (`buildkite.com/...`) require authentication and will return 403 if fetched directly via `WebFetch`, `curl`, or any HTTP client.
**Never fetch buildkite.com URLs directly.**

When you encounter a Buildkite URL (in PR descriptions, review comments, CI check links, or anywhere else):

1. Parse the URL to extract the pipeline slug and build number: `buildkite.com/elastic/<pipeline>/builds/<number>`
2. Use `bk` CLI to get the same information: `bk build view <number> -p <pipeline>`
3. For job logs or artifacts, follow the Failure Debugging Workflow below.

This applies during any workflow — reviews, PR fix, investigation, or standalone queries.

## Setup

Install the `bk` CLI via Homebrew:

```bash
brew tap buildkite/buildkite && brew install buildkite/buildkite/bk
bk configure
```

## Command reference

Build, job, artifact, pipeline, agent, auth/config, and the `bk api` escape hatch commands live in `references/bk-commands.md`.
Load it whenever you need a command not shown in the Failure Debugging Workflow below.

## Failure Debugging Workflow

When a build fails, follow this sequence:

1. Find the failed build: `bk build list -p SLUG --state failed`

2. View build details: `bk build view BUILD_NUMBER -p SLUG`

3. List jobs to find the failed one: `bk job list -p SLUG --state failed`

4. Get the failed job's log: `bk job log JOB_UUID -p SLUG -b BUILD_NUMBER`.
   Done when the failing step's error signature is located in the log.

5. List artifacts if available: `bk artifacts list BUILD_NUMBER -p SLUG`. Done when relevant artifacts are listed or confirmed absent.

For detailed debugging patterns, load `references/build-debugging.md`.

## Output Conventions

- `bk` outputs text/table format by default. Use `--json`, `--yaml`, or `-o json` for machine-readable output.
- When inside a git repo with a configured pipeline, `-p` can often be omitted (auto-detected from the repo).
- Use `bk api` for REST API endpoints not covered by direct commands.
  `bk api` auto-prepends the organization prefix, so use org-relative paths:

```bash
bk api /pipelines | jq '.[].slug'
bk api /pipelines/SLUG/builds | jq '.[0]'
```

## Reference Files

| Reference                     | When to Load                           |
| ----------------------------- | -------------------------------------- |
| references/bk-commands.md     | Full bk CLI command reference needed   |
| references/build-debugging.md | Debugging build failures in depth      |
| references/troubleshooting.md | Auth failures, CLI errors, rate limits |
