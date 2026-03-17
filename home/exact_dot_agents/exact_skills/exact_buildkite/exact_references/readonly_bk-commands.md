# Buildkite CLI — Command Reference

Full reference for the `buildkite` wrapper (routes to the `bk` CLI with
auto-setup). For quick examples, see SKILL.md.

---

## Authentication & Config

Setup is automatic — the `buildkite` wrapper runs `scripts/setup` on first use.

```bash
# Show current authenticated user
buildkite whoami

# Switch between configured profiles/orgs
buildkite use PROFILE_NAME
```

---

## Builds

```bash
# List builds (most recent first)
buildkite build list --pipeline SLUG
buildkite build list --pipeline SLUG --state failed
buildkite build list --pipeline SLUG --state running
buildkite build list --pipeline SLUG --branch BRANCH_NAME

# View a specific build
buildkite build view BUILD_NUMBER --pipeline SLUG

# Create (trigger) a new build
buildkite build create --pipeline SLUG --branch BRANCH --message "MESSAGE"
buildkite build create --pipeline SLUG --branch BRANCH --commit HEAD --message "MESSAGE"

# Rebuild (retry) a build
buildkite build rebuild BUILD_NUMBER --pipeline SLUG

# Cancel a running build
buildkite build cancel BUILD_NUMBER --pipeline SLUG

# Download build resources
buildkite build download BUILD_NUMBER --pipeline SLUG
```

---

## Jobs

```bash
# List jobs within a build
buildkite job list --build BUILD_NUMBER --pipeline SLUG

# View job log output
buildkite job log JOB_ID
```

---

## Pipelines

```bash
# List all pipelines in the org
buildkite pipeline list

# View pipeline details
buildkite pipeline view SLUG
```

---

## Artifacts

```bash
# List artifacts for a build
buildkite artifacts list --build BUILD_NUMBER --pipeline SLUG

# Download artifacts
buildkite artifacts download --build BUILD_NUMBER --pipeline SLUG
buildkite artifacts download --build BUILD_NUMBER --pipeline SLUG --path "GLOB_PATTERN"
```

---

## Agents

```bash
# List connected agents
buildkite agent list
```

---

## API Escape Hatch

For any Buildkite REST API endpoint not covered by direct commands, use
`buildkite api`:

```bash
# GET request (default)
buildkite api /v2/organizations/ORG/pipelines

# With jq for extraction
buildkite api /v2/organizations/ORG/pipelines | jq '.[].slug'

# GET with query params
buildkite api "/v2/organizations/ORG/pipelines/SLUG/builds?state=failed&per_page=5"

# POST request
buildkite api --method POST /v2/organizations/ORG/pipelines/SLUG/builds \
  --body '{"branch": "main", "message": "API triggered"}'
```

### Common REST API Endpoints

| Endpoint                                                             | Description              |
| -------------------------------------------------------------------- | ------------------------ |
| `/v2/organizations/ORG/pipelines`                                    | List pipelines           |
| `/v2/organizations/ORG/pipelines/SLUG/builds`                        | List builds for pipeline |
| `/v2/organizations/ORG/pipelines/SLUG/builds/NUMBER`                 | Get build details        |
| `/v2/organizations/ORG/pipelines/SLUG/builds/NUMBER/jobs/JOB_ID/log` | Get job log              |
| `/v2/organizations/ORG/agents`                                       | List agents              |

---

## Output Tips

- `buildkite` outputs JSON by default. Always pipe through `jq` for readability
  or extraction.
- Use `jq -r` for raw string output (no quotes).
- Chain with `| jq '.[0]'` to get the most recent item from a list.
- Use `buildkite api` + `jq` for advanced filtering the CLI doesn't support
  natively.
