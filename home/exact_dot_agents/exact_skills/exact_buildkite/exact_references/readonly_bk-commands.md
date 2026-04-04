# Buildkite CLI — Command Reference

Full reference for the `bk` CLI (v3.32.2). For quick examples, see SKILL.md.

---

## Authentication & Config

```bash
# Check current auth status
bk auth status

# Login (interactive)
bk auth login

# Switch to a different organization
bk auth switch ORG_SLUG

# List configured organizations
bk org list

# Get/set config values
bk config list
bk config get KEY
bk config set KEY VALUE
```

---

## Builds

All build commands accept `-p SLUG` (`--pipeline`). When inside a git repo with a configured pipeline, `-p` is often auto-detected.

```bash
# List builds (default: 50, text output)
bk build list -p SLUG
bk build list -p SLUG --state failed
bk build list -p SLUG --state running
bk build list -p SLUG --branch BRANCH
bk build list -p SLUG --since 1h
bk build list -p SLUG --creator alice@company.com
bk build list -p SLUG --duration ">20m"
bk build list -p SLUG --limit 200

# View a specific build (omit number for most recent on current branch)
bk build view BUILD_NUMBER -p SLUG
bk build view -p SLUG --mine
bk build view -p SLUG -b BRANCH

# Create (trigger) a new build
bk build create -p SLUG -b BRANCH -m "MESSAGE"
bk build create -p SLUG -b BRANCH -c HEAD -m "MESSAGE"
bk build create -p SLUG -e "FOO=BAR" -M "key=value"

# Rebuild (retry) a build
bk build rebuild BUILD_NUMBER -p SLUG

# Cancel a running build
bk build cancel BUILD_NUMBER -p SLUG

# Watch a build in real-time
bk build watch BUILD_NUMBER -p SLUG
bk build watch -p SLUG --interval 5

# Download build resources
bk build download BUILD_NUMBER -p SLUG
```

---

## Jobs

```bash
# List jobs (filter by pipeline, state, queue, duration)
bk job list -p SLUG --state failed
bk job list -p SLUG --queue QUEUE_NAME
bk job list -p SLUG --duration ">10m"
bk job list -p SLUG --since 1h --order-by duration

# View job log (requires pipeline + build number)
bk job log JOB_UUID -p SLUG -b BUILD_NUMBER
bk job log JOB_UUID -p SLUG -b BUILD_NUMBER --no-timestamps

# Retry a failed job
bk job retry JOB_UUID

# Cancel a job
bk job cancel JOB_UUID
```

---

## Pipelines

```bash
# List all pipelines in the org (default: 100)
bk pipeline list
bk pipeline list --name PATTERN
bk pipeline list --repo REPO_URL

# View pipeline details
bk pipeline view SLUG
bk pipeline view SLUG -w  # open in browser

# Create a new pipeline
bk pipeline create "My Pipeline" -p SLUG

# Validate a pipeline YAML
bk pipeline validate
```

---

## Artifacts

```bash
# List artifacts for a build (build number is positional)
bk artifacts list BUILD_NUMBER -p SLUG
bk artifacts list BUILD_NUMBER -p SLUG --job JOB_UUID

# Download an artifact by UUID
bk artifacts download ARTIFACT_UUID
```

---

## Agents

```bash
# List connected agents
bk agent list

# View agent details
bk agent view AGENT_ID

# Pause / resume / stop an agent
bk agent pause AGENT_ID
bk agent resume AGENT_ID
bk agent stop AGENT_ID
```

---

## API Escape Hatch

For any Buildkite REST API endpoint not covered by direct commands. `bk api` auto-prepends the org path, so use org-relative paths.

```bash
# GET (default method)
bk api /pipelines
bk api /pipelines/SLUG/builds

# With jq for extraction
bk api /pipelines | jq '.[].slug'
bk api /pipelines/SLUG/builds | jq '.[0].number'

# GET with query params
bk api "/pipelines/SLUG/builds?state=failed&per_page=5"

# POST request
bk api -X POST /pipelines/SLUG/builds \
  -d '{"branch": "main", "message": "API triggered"}'

# GraphQL query from file
bk api --file query.graphql
```

### Common REST API Paths (org-relative)

| Path                                            | Description              |
| ----------------------------------------------- | ------------------------ |
| `/pipelines`                                    | List pipelines           |
| `/pipelines/SLUG/builds`                        | List builds for pipeline |
| `/pipelines/SLUG/builds/NUMBER`                 | Get build details        |
| `/pipelines/SLUG/builds/NUMBER/jobs/JOB_ID/log` | Get job log              |
| `/agents`                                       | List agents              |

---

## Output Tips

- `bk` outputs text/table format by default.
- Use `--json`, `--yaml`, or `-o json` for machine-readable output.
- Use `jq -r` for raw string output (no quotes).
- Chain with `| jq '.[0]'` to get the most recent item from a list.
