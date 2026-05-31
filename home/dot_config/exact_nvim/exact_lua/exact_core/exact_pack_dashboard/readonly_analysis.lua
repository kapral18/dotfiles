-- Facade over the analysis submodules. The rest of the dashboard requires
-- `core.pack_dashboard.analysis` and calls the names re-exported here; the
-- concrete logic lives in the cohesive submodules under `analysis/`:
--   version  - spec/checkout version predicates, drift, risky `*` pins
--   gitcmd   - cached `git tag`/`git log` shell-outs
--   signals  - conventional-commit message classification
--   url      - source/repo/compare URL parsing
local semver = require("core.pack.semver")
local version = require("core.pack_dashboard.analysis.version")
local gitcmd = require("core.pack_dashboard.analysis.gitcmd")
local signals = require("core.pack_dashboard.analysis.signals")
local url = require("core.pack_dashboard.analysis.url")

local semver_delta = semver.semver_delta

local M = {}

-- Ties version tags, semver delta, and commit signals together into a single
-- breaking-change verdict. Mutates `p_data` with the resolved versions, delta,
-- commit signal summary, and a human-readable `risk_reason`.
local function infer_breaking_status(p_data)
  if p_data.status ~= "update" then
    return nil
  end

  local before_version = p_data.current_version or gitcmd.tag_on_revision(p_data.path, p_data.rev_before)
  local after_version = p_data.target_version or gitcmd.tag_on_revision(p_data.path, p_data.rev_after)
  p_data.current_version = before_version
  p_data.target_version = after_version

  local semver_change = semver_delta(before_version, after_version)
  p_data.semver_delta = semver_change

  local range_messages = gitcmd.commit_messages_between(p_data.path, p_data.rev_before, p_data.rev_after)
  local message_text = (type(range_messages) == "string" and range_messages ~= "") and range_messages
    or (p_data.pending_updates or "")

  local message_summary = signals.classify_commit_signals(message_text)
  p_data.commit_signal = signals.format_commit_signals(message_summary)

  if message_summary.has_breaking then
    p_data.risk_reason = "commit messages include BREAKING signal"
    return true
  end

  if semver_change == "major" then
    p_data.risk_reason = "semver major bump"
    return true
  end

  if semver_change == "minor" or semver_change == "patch" or semver_change == "same" then
    p_data.risk_reason = "semver " .. semver_change .. " bump"
    return false
  end

  if message_summary.feat > 0 or message_summary.refactor > 0 or message_summary.perf > 0 then
    p_data.risk_reason = "non-semver refs with feat/refactor/perf commits"
    return nil
  end

  if
    message_summary.fix > 0
    and message_summary.feat == 0
    and message_summary.refactor == 0
    and message_summary.perf == 0
  then
    p_data.risk_reason = "non-semver refs with fix-only commit messages"
    return false
  end

  if message_summary.docs > 0 or message_summary.chore > 0 or message_summary.has_deprecation then
    p_data.risk_reason = "non-semver refs with docs/chore/deprecation signals"
    return nil
  end

  p_data.risk_reason = "insufficient semver/commit signal"
  return nil
end

M.is_commit_string = version.is_commit_string
M.compute_version_drift = version.compute_version_drift
M.detect_risky_star_pin = version.detect_risky_star_pin
M.refresh_version_flags_async = version.refresh_version_flags_async
M.short_rev = version.short_rev
M.commit_subjects_between = gitcmd.commit_subjects_between
M.infer_breaking_status = infer_breaking_status
M.source_to_compare_url = url.source_to_compare_url
M.source_to_repo_url = url.source_to_repo_url
M.repo_to_compare_url = url.repo_to_compare_url

return M
