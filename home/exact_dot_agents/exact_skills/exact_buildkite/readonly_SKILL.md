---
name: buildkite
description: |-
  Buildkite CI/CD integration. Use when checking build status, triggering
  builds, reading build logs, debugging CI failures, or managing pipelines.
  Trigger words include "buildkite", "build", "CI", "build failed". Only for
  elastic org repos.
allowed-tools: Bash(bk:*)
---

# Buildkite — CI/CD

## Setup

Install the `bk` CLI via Homebrew:

```bash
brew tap buildkite/buildkite && brew install buildkite/buildkite/bk
bk configure
```

## Build Operations

```bash
# List recent builds (default: 50)
bk build list -p SLUG

# List failed builds
bk build list -p SLUG --state failed

# List builds on a branch
bk build list -p SLUG --branch main

# View build details (omit number for most recent on current branch)
bk build view BUILD_NUMBER -p SLUG

# Create (trigger) a new build
bk build create -p SLUG -b BRANCH -m "MESSAGE"

# Rebuild a build
bk build rebuild BUILD_NUMBER -p SLUG

# Cancel a running build
bk build cancel BUILD_NUMBER -p SLUG

# Watch a build in real-time
bk build watch BUILD_NUMBER -p SLUG
```

## Job & Log Operations

```bash
# List jobs (filter by pipeline, state, queue, duration)
bk job list -p SLUG --state failed

# View job log (requires pipeline + build number)
bk job log JOB_UUID -p SLUG -b BUILD_NUMBER

# Retry a failed job
bk job retry JOB_UUID
```

## Artifact Operations

```bash
# List artifacts for a build
bk artifacts list BUILD_NUMBER -p SLUG

# Download an artifact by UUID
bk artifacts download ARTIFACT_UUID
```

## Pipeline Operations

```bash
# List all pipelines
bk pipeline list

# Filter pipelines by name
bk pipeline list --name PATTERN

# View pipeline details
bk pipeline view SLUG
```

## Auth & Config

```bash
# Check current auth status
bk auth status

# Switch organization
bk auth switch ORG_SLUG

# Show CLI version
bk version
```

## Failure Debugging Workflow

When a build fails, follow this sequence:

1. Find the failed build: `bk build list -p SLUG --state failed`

2. View build details: `bk build view BUILD_NUMBER -p SLUG`

3. List jobs to find the failed one: `bk job list -p SLUG --state failed`

4. Get the failed job's log: `bk job log JOB_UUID -p SLUG -b BUILD_NUMBER`

5. List artifacts if available: `bk artifacts list BUILD_NUMBER -p SLUG`

For detailed debugging patterns, load `references/build-debugging.md`.

## Triage (Wrapper Extension)

The `triage` subcommand is provided by the wrapper script at
`skills/buildkite/scripts/buildkite`. It fetches failed builds and categorizes
failures by pattern:

```bash
skills/buildkite/scripts/buildkite triage PIPELINE_SLUG
skills/buildkite/scripts/buildkite triage PIPELINE_SLUG --build 456
skills/buildkite/scripts/buildkite triage PIPELINE_SLUG --last 5
```

## Output Conventions

- `bk` outputs text/table format by default. Use `--json`, `--yaml`, or
  `-o json` for machine-readable output.
- When inside a git repo with a configured pipeline, `-p` can often be omitted
  (auto-detected from the repo).
- Use `bk api` for REST API endpoints not covered by direct commands. `bk api`
  auto-prepends the organization prefix, so use org-relative paths:

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
