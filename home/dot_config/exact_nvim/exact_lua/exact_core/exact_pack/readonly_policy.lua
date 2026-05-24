-- Version policy and tag/branch heuristic engine for the vim.pack loader.
-- Extracted from the dashboard so the decision logic (git tag analysis,
-- 4-gate release-cadence heuristic, on-disk JSON cache under stdpath("state"),
-- async + synchronous refresh, invalidate/rebuild) can be unit-tested by
-- loading this single file and evolved without touching UI code.
--
-- Contracts:
--   * `version_policy_path()` — returns the stdpath("state") json path.
--   * `load_version_policy()` / `write_version_policy(plugins)` — read/write the
--     { schema, generated_at, plugins = { name = {strategy, ...}, ... } } cache.
--   * `refresh_version_policy_if_needed()` (sync) and `_async(callback)` —
--     recompute only missing/expired entries using the heuristic; incremental
--     when possible.
--   * `invalidate_version_policy(name?)` / `rebuild_version_policy(name?)` —
--     force re-evaluation for one or all plugins (used by :PackPolicyRebuild).
--   * `decide_tag_strategy(gitdir, name)` (internal) — returns the strategy table
--     after applying the four gates (min tags, lag vs avg, tag age, abs cap).
--
-- The heuristics read vim.g.pack_policy_* overrides and use only vim.system +
-- vim.pack + json. No buffers, windows, keymaps, or highlights.
local M = {}

local semver = require("core.pack.semver")
local parse_release_tag = semver.parse_release_tag

function M.version_policy_path()
  return vim.fn.stdpath("state") .. "/pack_version_policy.json"
end

local function version_policy_path()
  return M.version_policy_path()
end

local function read_tag_dates(path)
  if type(path) ~= "string" or path == "" then
    return {}
  end
  local result = vim
    .system({
      "git",
      "-C",
      path,
      "for-each-ref",
      "--sort=-creatordate",
      "--format=%(refname:short)\t%(creatordate:unix)",
      "refs/tags",
    }, { text = true })
    :wait()
  if result.code ~= 0 or type(result.stdout) ~= "string" or result.stdout == "" then
    return {}
  end

  local out = {}
  for _, line in ipairs(vim.split(result.stdout, "\n", { trimempty = true })) do
    local tag, ts = line:match("^(.-)\t(%d+)$")
    if tag and ts and parse_release_tag(tag) ~= nil then
      out[#out + 1] = { tag = tag, ts = tonumber(ts) or 0 }
    end
  end
  return out
end

local function tags_reachable_from(path, ref)
  if type(path) ~= "string" or path == "" or type(ref) ~= "string" or ref == "" then
    return nil
  end
  local result = vim.system({ "git", "-C", path, "tag", "--merged", ref }, { text = true }):wait()
  if result.code ~= 0 or type(result.stdout) ~= "string" then
    return nil
  end
  local set = {}
  for _, line in ipairs(vim.split(result.stdout, "\n", { trimempty = true })) do
    local trimmed = vim.trim(line)
    if trimmed ~= "" then
      set[trimmed] = true
    end
  end
  return set
end

local function latest_semver_tag(tags_with_dates, reachable_set)
  local best = nil
  local best_v = nil
  local best_reachable = nil
  local best_reachable_v = nil
  for _, item in ipairs(tags_with_dates or {}) do
    local tag = item.tag
    local v = parse_release_tag(tag)
    if v ~= nil then
      if not best_v or vim.version.gt(v, best_v) then
        best = item
        best_v = v
      end
      if reachable_set and reachable_set[tag] then
        if not best_reachable_v or vim.version.gt(v, best_reachable_v) then
          best_reachable = item
          best_reachable_v = v
        end
      end
    end
  end
  if reachable_set and best_reachable then
    return best_reachable
  end
  return best
end

local function commit_count_between(path, from_ref, to_ref)
  if type(path) ~= "string" or path == "" then
    return nil
  end
  local result = vim
    .system({ "git", "-C", path, "rev-list", "--count", from_ref .. ".." .. to_ref }, { text = true })
    :wait()
  if result.code ~= 0 or type(result.stdout) ~= "string" then
    return nil
  end
  return tonumber(vim.trim(result.stdout))
end

local function origin_head_ref(path)
  if type(path) ~= "string" or path == "" then
    return nil
  end
  local result = vim
    .system({ "git", "-C", path, "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD" }, { text = true })
    :wait()
  if result.code ~= 0 or type(result.stdout) ~= "string" then
    return nil
  end
  local ref = vim.trim(result.stdout)
  return ref ~= "" and ref or nil
end

local function avg_commits_per_release(path, tags_with_dates, limit)
  limit = tonumber(limit) or 6
  if limit < 3 then
    limit = 3
  end
  if type(tags_with_dates) ~= "table" or #tags_with_dates < 2 then
    return nil
  end

  local tags = {}
  for _, item in ipairs(tags_with_dates) do
    if type(item) == "table" and type(item.tag) == "string" and item.tag ~= "" then
      tags[#tags + 1] = item.tag
    end
    if #tags >= limit then
      break
    end
  end
  if #tags < 2 then
    return nil
  end

  local weighted_sum = 0
  local weight_total = 0
  for i = 1, (#tags - 1) do
    local n = commit_count_between(path, tags[i + 1], tags[i])
    if n and n > 0 then
      local weight = 1 / i
      weighted_sum = weighted_sum + n * weight
      weight_total = weight_total + weight
    end
  end
  if weight_total == 0 then
    return nil
  end
  return math.floor(weighted_sum / weight_total)
end

local function current_head_tag(path)
  if type(path) ~= "string" or path == "" then
    return nil
  end
  local result = vim
    .system({ "git", "-C", path, "describe", "--tags", "--exact-match", "HEAD" }, { text = true })
    :wait()
  if result.code ~= 0 or type(result.stdout) ~= "string" then
    return nil
  end
  local tag = vim.trim(result.stdout)
  if tag ~= "" and parse_release_tag(tag) ~= nil then
    return tag
  end
  return nil
end

local function decide_tag_strategy(path, _name)
  local tag_dates = read_tag_dates(path)
  if #tag_dates == 0 then
    return { strategy = "branch", semver_tags = false, reason = "no semver tags" }
  end

  local head_ref = origin_head_ref(path) or "origin/HEAD"
  local reachable = tags_reachable_from(path, head_ref)
  local latest = latest_semver_tag(tag_dates, reachable)
  if not latest then
    return { strategy = "branch", semver_tags = false, reason = "no semver tags" }
  end

  local commits_since = commit_count_between(path, latest.tag, head_ref)
  local cur_tag = current_head_tag(path)
  if not commits_since then
    return {
      strategy = "tags",
      semver_tags = true,
      latest_tag = latest.tag,
      latest_tag_ts = latest.ts,
      current_tag = cur_tag,
      tag_count = #tag_dates,
      reason = "cannot count commits since tag",
    }
  end

  local base = {
    semver_tags = true,
    latest_tag = latest.tag,
    latest_tag_ts = latest.ts,
    current_tag = cur_tag,
    tag_count = #tag_dates,
    commits_since_tag = commits_since,
  }

  if commits_since == 0 then
    base.strategy = "tags"
    base.reason = "branch tip is at latest tag"
    return base
  end

  local min_tags = tonumber(vim.g.pack_policy_min_tags) or 3
  local multiplier = tonumber(vim.g.pack_policy_commit_lag_multiplier) or 1.5
  local abs_cap = tonumber(vim.g.pack_policy_max_commits_since_tag) or 150
  local sparse_threshold = tonumber(vim.g.pack_policy_sparse_tag_threshold) or 30
  local max_tag_age_days = tonumber(vim.g.pack_policy_max_tag_age_days) or 180

  -- Gate 1: not enough release history to trust an average.
  if #tag_dates < min_tags then
    if commits_since > sparse_threshold then
      base.strategy = "branch"
      base.reason = "insufficient release history ("
        .. #tag_dates
        .. " tags), "
        .. commits_since
        .. " unreleased commits"
    else
      base.strategy = "tags"
      base.reason = "insufficient release history, few unreleased commits"
    end
    return base
  end

  -- Gate 2: compare against average release size.
  local avg = avg_commits_per_release(path, tag_dates, 6)
  base.avg_commits_per_release = avg
  if avg and avg > 0 and commits_since > (avg * multiplier) then
    base.strategy = "branch"
    base.reason = "commits since tag (" .. commits_since .. ") exceed avg release size (" .. avg .. ")"
    return base
  end

  -- Gate 3: time since latest tag — stale releases indicate abandoned tagging.
  if latest.ts and latest.ts > 0 then
    local age_days = (os.time() - latest.ts) / 86400
    base.tag_age_days = math.floor(age_days)
    if age_days > max_tag_age_days and commits_since > 0 then
      base.strategy = "branch"
      base.reason = "latest tag is " .. math.floor(age_days) .. "d old with " .. commits_since .. " unreleased commits"
      return base
    end
  end

  -- Gate 4: absolute cap as safety net.
  if commits_since > abs_cap then
    base.strategy = "branch"
    base.reason = "too many unreleased commits (" .. commits_since .. ")"
    return base
  end

  base.strategy = "tags"
  base.reason = "within expected release cadence"
  return base
end

function M.load_version_policy()
  local path = version_policy_path()
  if vim.fn.filereadable(path) ~= 1 then
    return nil
  end

  local ok_read, lines = pcall(vim.fn.readfile, path)
  if not ok_read or type(lines) ~= "table" or #lines == 0 then
    return nil
  end

  local ok_decode, decoded = pcall(vim.json.decode, table.concat(lines, "\n"))
  if not ok_decode or type(decoded) ~= "table" then
    return nil
  end

  if type(decoded.plugins) ~= "table" then
    decoded.plugins = {}
  end

  decoded.schema = tonumber(decoded.schema) or 0
  decoded.generated_at = tonumber(decoded.generated_at)
  return decoded
end

local function load_version_policy()
  return M.load_version_policy()
end

function M.write_version_policy(plugins)
  if type(plugins) ~= "table" then
    return false
  end
  local payload = {
    schema = 3,
    generated_at = os.time(),
    plugins = plugins,
  }
  local ok_json, encoded = pcall(vim.json.encode, payload)
  if not ok_json or type(encoded) ~= "string" or encoded == "" then
    return false
  end
  local ok_write = pcall(vim.fn.writefile, { encoded }, version_policy_path())
  return ok_write and true or false
end

local function write_version_policy(plugins)
  return M.write_version_policy(plugins)
end

local POLICY_MAX_AGE = 60 * 60 * 24 * 3

-- Returns one of:
--   "fresh"        — cache is still valid, no work needed
--   "full"         — cache expired or schema mismatch, recompute every plugin
--   "incremental"  — cache valid but missing some plugins; only compute those
local function policy_refresh_mode(existing, plugin_names)
  if type(plugin_names) ~= "table" then
    return "full"
  end
  if type(existing) ~= "table" or existing.schema ~= 3 or type(existing.plugins) ~= "table" then
    return "full"
  end

  local generated_at = tonumber(existing.generated_at) or 0
  if generated_at > 0 and (os.time() - generated_at) > POLICY_MAX_AGE then
    return "full"
  end

  for _, name in ipairs(plugin_names) do
    if existing.plugins[name] == nil then
      return "incremental"
    end
  end

  return "fresh"
end

-- True when policy refresh is already running under `schedule_wrap`. Prevents
-- concurrent refreshes when the async path and a sync fallback overlap.
local policy_refresh_in_progress = false

-- Synchronous refresh used by user-initiated paths (`PackSync`, `PackStatus`,
-- post-apply refresh) where the user is already waiting. Incremental when the
-- only change is new plugins; full when time-expired. Missing plugin entries
-- are filled in-place instead of recomputing every entry.
function M.refresh_version_policy_if_needed()
  local ok, plug_data = pcall(vim.pack.get, nil, { info = false })
  if not ok or type(plug_data) ~= "table" then
    return false
  end

  local names = {}
  for _, p in ipairs(plug_data) do
    if p and p.spec and type(p.spec.name) == "string" and p.spec.name ~= "" then
      names[#names + 1] = p.spec.name
    end
  end

  local existing = load_version_policy()
  local mode = policy_refresh_mode(existing, names)
  if mode == "fresh" then
    return true
  end

  local plugins = {}
  if mode == "incremental" and type(existing) == "table" and type(existing.plugins) == "table" then
    for name, info in pairs(existing.plugins) do
      plugins[name] = info
    end
  end

  local name_set = {}
  for _, name in ipairs(names) do
    name_set[name] = true
  end

  if mode == "incremental" then
    -- Drop entries for plugins that were removed so the on-disk cache stays
    -- in sync with the current plugin set.
    for name in pairs(plugins) do
      if not name_set[name] then
        plugins[name] = nil
      end
    end
  end

  for _, p in ipairs(plug_data) do
    local name = p and p.spec and p.spec.name
    local path = p and p.path
    if type(name) == "string" and name ~= "" and type(path) == "string" and path ~= "" then
      if mode == "full" or plugins[name] == nil then
        plugins[name] = decide_tag_strategy(path, name)
      end
    end
  end

  return write_version_policy(plugins)
end

-- Async variant used by the startup bootstrap path. Processes one plugin per
-- scheduled tick so the UI can redraw between git shell-outs. On macOS with
-- 86 plugins the synchronous path blocks for several seconds on the first
-- cold run; this spreads the cost across event-loop iterations and surfaces
-- progress through `vim.notify`. When `callback` is provided it's invoked on
-- the main loop after the write (or immediately on noop).
function M.refresh_version_policy_async(callback)
  if policy_refresh_in_progress then
    if callback then
      vim.schedule(function()
        callback(false, "busy")
      end)
    end
    return false
  end

  local ok, plug_data = pcall(vim.pack.get, nil, { info = false })
  if not ok or type(plug_data) ~= "table" then
    if callback then
      vim.schedule(function()
        callback(false, "no-plugins")
      end)
    end
    return false
  end

  local names = {}
  for _, p in ipairs(plug_data) do
    if p and p.spec and type(p.spec.name) == "string" and p.spec.name ~= "" then
      names[#names + 1] = p.spec.name
    end
  end

  local existing = load_version_policy()
  local mode = policy_refresh_mode(existing, names)
  if mode == "fresh" then
    if callback then
      vim.schedule(function()
        callback(true, "fresh")
      end)
    end
    return true
  end

  local plugins = {}
  if mode == "incremental" and type(existing) == "table" and type(existing.plugins) == "table" then
    for name, info in pairs(existing.plugins) do
      plugins[name] = info
    end
  end

  local name_set = {}
  for _, name in ipairs(names) do
    name_set[name] = true
  end
  if mode == "incremental" then
    for name in pairs(plugins) do
      if not name_set[name] then
        plugins[name] = nil
      end
    end
  end

  local pending = {}
  for _, p in ipairs(plug_data) do
    local name = p and p.spec and p.spec.name
    local path = p and p.path
    if type(name) == "string" and name ~= "" and type(path) == "string" and path ~= "" then
      if mode == "full" or plugins[name] == nil then
        pending[#pending + 1] = { name = name, path = path }
      end
    end
  end

  if #pending == 0 then
    local wrote = write_version_policy(plugins)
    if callback then
      vim.schedule(function()
        callback(wrote, "no-work")
      end)
    end
    return wrote
  end

  policy_refresh_in_progress = true
  local total = #pending
  local index = 0

  local function step()
    if not policy_refresh_in_progress then
      return
    end
    index = index + 1
    if index > total then
      policy_refresh_in_progress = false
      local wrote = write_version_policy(plugins)
      if callback then
        callback(wrote, mode)
      end
      return
    end

    local entry = pending[index]
    local ok_entry, policy = pcall(decide_tag_strategy, entry.path, entry.name)
    if ok_entry and type(policy) == "table" then
      plugins[entry.name] = policy
    end
    vim.schedule(step)
  end

  vim.schedule(step)
  return true
end

-- Drop a single plugin entry (or everything when `name == nil`) from the
-- on-disk version policy so the next refresh recomputes it from scratch.
-- Called by `:PackPolicyRebuild` and anything else that wants to force the
-- heuristic to re-evaluate (e.g. after the plugin set changes).
function M.invalidate_version_policy(name)
  local existing = load_version_policy()
  if type(existing) ~= "table" or type(existing.plugins) ~= "table" then
    return true
  end
  if type(name) == "string" and name ~= "" then
    if existing.plugins[name] == nil then
      return true
    end
    existing.plugins[name] = nil
    return write_version_policy(existing.plugins)
  end
  local path = version_policy_path()
  if vim.fn.filereadable(path) == 1 then
    pcall(vim.fn.delete, path)
  end
  return true
end

-- Recompute the policy entry for a single plugin (or every plugin) and write
-- the result to disk. Used by `:PackPolicyRebuild` and other code paths that
-- want to force a reread after changing mode/pins. Runs synchronously so the
-- caller can surface the result immediately; the caller decides whether to
-- block the UI (user-initiated via command = fine, startup = use async).
function M.rebuild_version_policy(name)
  M.invalidate_version_policy(name)
  return M.refresh_version_policy_if_needed()
end

return M
