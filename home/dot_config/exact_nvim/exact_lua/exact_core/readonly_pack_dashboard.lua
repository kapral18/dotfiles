local M = {}

local configured = false
local pack_report_cache = {
  plugins = {},
  updated_at = nil,
  mode = nil,
  last_online_at = nil,
  last_offline_at = nil,
  last_applied_at = nil,
  last_applied_count = 0,
  last_check_counts = nil,
}
local dashboard_ui_cache = {
  filter_mode = "all",
  sort_mode = "status",
  search_text = nil,
  selected_names = {},
}
local persisted_state_loaded = false
local dashboard_ns = vim.api.nvim_create_namespace("core.pack_dashboard")

local function persisted_state_path()
  return vim.fn.stdpath("state") .. "/pack_dashboard_state.json"
end

function M.version_policy_path()
  return vim.fn.stdpath("state") .. "/pack_version_policy.json"
end

local function version_policy_path()
  return M.version_policy_path()
end

function M.parse_release_tag(tag)
  if type(tag) ~= "string" then
    return nil
  end
  local t = vim.trim(tag)
  if t == "" then
    return nil
  end

  -- Gate semver parsing to avoid coercing "garbage" tags like "nerd-v2-compat"
  -- into fake versions. Still accept common tag formats like "v1.2.3",
  -- "1.2.3", and two-part tags like "0.7" (coerced to "0.7.0").
  local looks_like_version = t:match("^v?%d+%.%d+%.%d+[%-%+].+$")
    or t:match("^v?%d+%.%d+%.%d+$")
    or t:match("^v?%d+%.%d+[%-%+].+$")
    or t:match("^v?%d+%.%d+$")
  if not looks_like_version then
    return nil
  end

  local ok, parsed = pcall(vim.version.parse, t, { strict = false })
  if ok then
    return parsed
  end
  return nil
end

local function parse_release_tag(tag)
  return M.parse_release_tag(tag)
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

local function should_refresh_policy(existing, plugin_names)
  if type(plugin_names) ~= "table" then
    return true
  end
  if type(existing) ~= "table" or existing.schema ~= 3 or type(existing.plugins) ~= "table" then
    return true
  end

  local generated_at = tonumber(existing.generated_at) or 0
  if generated_at > 0 and (os.time() - generated_at) > POLICY_MAX_AGE then
    return true
  end

  for _, name in ipairs(plugin_names) do
    if existing.plugins[name] == nil then
      return true
    end
  end

  return false
end

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
  if not should_refresh_policy(existing, names) then
    return true
  end

  local plugins = {}
  for _, p in ipairs(plug_data) do
    local name = p and p.spec and p.spec.name
    local path = p and p.path
    if type(name) == "string" and name ~= "" and type(path) == "string" and path ~= "" then
      plugins[name] = decide_tag_strategy(path, name)
    end
  end

  return write_version_policy(plugins)
end

local function refresh_version_policy_if_needed()
  return M.refresh_version_policy_if_needed()
end

local function normalize_epoch(value)
  if type(value) ~= "number" then
    return nil
  end
  if value <= 0 then
    return nil
  end
  return math.floor(value)
end

local function normalize_mode(value, allowed, fallback)
  if type(value) ~= "string" then
    return fallback
  end
  return allowed[value] and value or fallback
end

local function normalize_selected_names(value)
  if type(value) ~= "table" then
    return {}
  end
  local out = {}
  local seen = {}
  for _, name in ipairs(value) do
    if type(name) == "string" and name ~= "" and not seen[name] then
      seen[name] = true
      out[#out + 1] = name
    end
  end
  table.sort(out)
  return out
end

local function write_persisted_state()
  local payload = {
    updated_at = normalize_epoch(pack_report_cache.updated_at),
    mode = pack_report_cache.mode,
    last_online_at = normalize_epoch(pack_report_cache.last_online_at),
    last_offline_at = normalize_epoch(pack_report_cache.last_offline_at),
    last_applied_at = normalize_epoch(pack_report_cache.last_applied_at),
    last_applied_count = tonumber(pack_report_cache.last_applied_count) or 0,
    last_check_counts = pack_report_cache.last_check_counts,
    plugins = pack_report_cache.plugins,
    ui = {
      filter_mode = dashboard_ui_cache.filter_mode,
      sort_mode = dashboard_ui_cache.sort_mode,
      search_text = dashboard_ui_cache.search_text,
      selected_names = dashboard_ui_cache.selected_names,
    },
  }
  local ok_json, encoded = pcall(vim.json.encode, payload)
  if not ok_json or type(encoded) ~= "string" or encoded == "" then
    return
  end
  pcall(vim.fn.writefile, { encoded }, persisted_state_path())
end

local function load_persisted_state_once()
  if persisted_state_loaded then
    return
  end
  persisted_state_loaded = true

  local path = persisted_state_path()
  if vim.fn.filereadable(path) ~= 1 then
    return
  end

  local ok_read, lines = pcall(vim.fn.readfile, path)
  if not ok_read or type(lines) ~= "table" or #lines == 0 then
    return
  end

  local ok_decode, decoded = pcall(vim.json.decode, table.concat(lines, "\n"))
  if not ok_decode or type(decoded) ~= "table" then
    return
  end

  pack_report_cache.updated_at = normalize_epoch(decoded.updated_at)
  pack_report_cache.last_online_at = normalize_epoch(decoded.last_online_at)
  pack_report_cache.last_offline_at = normalize_epoch(decoded.last_offline_at)
  pack_report_cache.last_applied_at = normalize_epoch(decoded.last_applied_at)
  pack_report_cache.last_applied_count = tonumber(decoded.last_applied_count) or 0
  if type(decoded.plugins) == "table" then
    local restored = {}
    for name, info in pairs(decoded.plugins) do
      if type(name) == "string" and type(info) == "table" then
        restored[name] = info
      end
    end
    pack_report_cache.plugins = restored
  end
  if type(decoded.last_check_counts) == "table" then
    pack_report_cache.last_check_counts = {
      update = tonumber(decoded.last_check_counts.update) or 0,
      same = tonumber(decoded.last_check_counts.same) or 0,
      error = tonumber(decoded.last_check_counts.error) or 0,
    }
  end

  if decoded.mode == "online" or decoded.mode == "offline" or decoded.mode == "unknown" then
    pack_report_cache.mode = decoded.mode
  end

  if type(decoded.ui) == "table" then
    dashboard_ui_cache.filter_mode =
      normalize_mode(decoded.ui.filter_mode, { all = true, updates = true, issues = true, selected = true }, "all")
    dashboard_ui_cache.sort_mode = normalize_mode(decoded.ui.sort_mode, { status = true, name = true }, "status")
    if type(decoded.ui.search_text) == "string" and decoded.ui.search_text ~= "" then
      dashboard_ui_cache.search_text = decoded.ui.search_text
    else
      dashboard_ui_cache.search_text = nil
    end
    dashboard_ui_cache.selected_names = normalize_selected_names(decoded.ui.selected_names)
  end
end

local function ensure_dashboard_highlights()
  local set_hl = vim.api.nvim_set_hl
  set_hl(0, "PackDashboardTitle", { default = true, link = "Title" })
  set_hl(0, "PackDashboardStats", { default = true, link = "Special" })
  set_hl(0, "PackDashboardMeta", { default = true, link = "Comment" })
  set_hl(0, "PackDashboardHeader", { default = true, link = "Identifier" })
  set_hl(0, "PackDashboardStatusUpdate", { default = true, link = "DiagnosticInfo" })
  set_hl(0, "PackDashboardStatusSame", { default = true, link = "String" })
  set_hl(0, "PackDashboardStatusError", { default = true, link = "DiagnosticError" })
  set_hl(0, "PackDashboardStatusUnknown", { default = true, link = "Comment" })
  set_hl(0, "PackDashboardRiskBreak", { default = true, link = "DiagnosticWarn" })
  set_hl(0, "PackDashboardRiskSafe", { default = true, link = "DiffAdd" })
  set_hl(0, "PackDashboardRiskUnknown", { default = true, link = "Comment" })
  set_hl(0, "PackDashboardLink", { default = true, link = "Underlined" })
  set_hl(0, "PackDashboardSelected", { default = true, link = "IncSearch" })
end

local function notify_err(msg)
  vim.schedule(function()
    vim.notify(msg, vim.log.levels.ERROR)
  end)
end

local function semver_major(version)
  if type(version) ~= "string" or version == "" then
    return nil
  end
  local major = version:match("^v?(%d+)%.") or version:match("^v?(%d+)$")
  return major and tonumber(major) or nil
end

local function semver_triplet(version)
  if type(version) ~= "string" or version == "" then
    return nil
  end
  local major, minor, patch = version:match("^v?(%d+)%.(%d+)%.(%d+)")
  if not major then
    major, minor = version:match("^v?(%d+)%.(%d+)")
    patch = "0"
  end
  if not major then
    major = version:match("^v?(%d+)$")
    minor = "0"
    patch = "0"
  end
  if not major then
    return nil
  end
  return {
    major = tonumber(major),
    minor = tonumber(minor) or 0,
    patch = tonumber(patch) or 0,
  }
end

local function semver_delta(before_version, after_version)
  local before_triplet = semver_triplet(before_version)
  local after_triplet = semver_triplet(after_version)
  if not before_triplet or not after_triplet then
    return nil
  end
  if after_triplet.major ~= before_triplet.major then
    return "major"
  end
  if after_triplet.minor ~= before_triplet.minor then
    return "minor"
  end
  if after_triplet.patch ~= before_triplet.patch then
    return "patch"
  end
  return "same"
end

local revision_tag_cache = {}
local commit_messages_cache = {}
local function tag_on_revision(path, rev)
  if type(path) ~= "string" or path == "" or type(rev) ~= "string" or rev == "" then
    return nil
  end
  local key = path .. "@" .. rev
  if revision_tag_cache[key] ~= nil then
    return revision_tag_cache[key]
  end

  local result = vim.system({ "git", "-C", path, "tag", "--points-at", rev }, { text = true }):wait()
  if result.code ~= 0 or type(result.stdout) ~= "string" then
    revision_tag_cache[key] = false
    return nil
  end

  local tags = {}
  for _, line in ipairs(vim.split(result.stdout, "\n", { trimempty = true })) do
    if line ~= "" then
      tags[#tags + 1] = line
    end
  end

  table.sort(tags, function(a, b)
    local ma, mb = semver_major(a) or -1, semver_major(b) or -1
    if ma ~= mb then
      return ma > mb
    end
    return a > b
  end)

  revision_tag_cache[key] = tags[1] or false
  return revision_tag_cache[key] or nil
end

local function commit_messages_between(path, rev_before, rev_after)
  if
    type(path) ~= "string"
    or path == ""
    or type(rev_before) ~= "string"
    or rev_before == ""
    or type(rev_after) ~= "string"
    or rev_after == ""
  then
    return nil
  end

  local key = path .. "@" .. rev_before .. ".." .. rev_after
  if commit_messages_cache[key] ~= nil then
    return commit_messages_cache[key] or nil
  end

  local result = vim
    .system({ "git", "-C", path, "log", "--format=%s%n%b", rev_before .. ".." .. rev_after }, { text = true })
    :wait()
  if result.code ~= 0 or type(result.stdout) ~= "string" then
    commit_messages_cache[key] = false
    return nil
  end

  local normalized = vim.trim(result.stdout)
  commit_messages_cache[key] = normalized ~= "" and normalized or false
  return commit_messages_cache[key] or nil
end

local commit_subjects_cache = {}
local function commit_subjects_between(path, rev_before, rev_after)
  if
    type(path) ~= "string"
    or path == ""
    or type(rev_before) ~= "string"
    or rev_before == ""
    or type(rev_after) ~= "string"
    or rev_after == ""
  then
    return nil
  end

  local key = path .. "@" .. rev_before .. ".." .. rev_after
  if commit_subjects_cache[key] ~= nil then
    return commit_subjects_cache[key] or nil
  end

  local result = vim
    .system({ "git", "-C", path, "log", "--format=%s", rev_before .. ".." .. rev_after }, { text = true })
    :wait()
  if result.code ~= 0 or type(result.stdout) ~= "string" then
    commit_subjects_cache[key] = false
    return nil
  end

  local subjects = {}
  for _, line in ipairs(vim.split(result.stdout, "\n", { trimempty = true })) do
    local trimmed = vim.trim(line)
    if trimmed ~= "" then
      subjects[#subjects + 1] = trimmed
    end
  end

  commit_subjects_cache[key] = #subjects > 0 and subjects or false
  return commit_subjects_cache[key] or nil
end

local function classify_commit_signals(text)
  local summary = {
    has_breaking = false,
    has_deprecation = false,
    feat = 0,
    fix = 0,
    refactor = 0,
    perf = 0,
    docs = 0,
    chore = 0,
  }
  if type(text) ~= "string" or text == "" then
    return summary
  end

  for _, raw in ipairs(vim.split(text, "\n", { trimempty = true })) do
    local line = vim.trim(raw):lower()
    if line ~= "" then
      if line:find("breaking change", 1, true) or line:find("breaking:", 1, true) or line:find("!:", 1, true) then
        summary.has_breaking = true
      end
      if line:find("deprecat", 1, true) then
        summary.has_deprecation = true
      end
      if line:match("^feat[%(:!]") or line:find(" feature", 1, true) then
        summary.feat = summary.feat + 1
      end
      if line:match("^fix[%(:!]") or line:find(" bugfix", 1, true) then
        summary.fix = summary.fix + 1
      end
      if line:match("^refactor[%(:!]") then
        summary.refactor = summary.refactor + 1
      end
      if line:match("^perf[%(:!]") or line:find(" performance", 1, true) then
        summary.perf = summary.perf + 1
      end
      if line:match("^docs[%(:!]") then
        summary.docs = summary.docs + 1
      end
      if line:match("^chore[%(:!]") then
        summary.chore = summary.chore + 1
      end
    end
  end

  return summary
end

local function format_commit_signals(summary)
  if type(summary) ~= "table" then
    return "none"
  end
  local parts = {}
  if summary.has_breaking then
    parts[#parts + 1] = "breaking"
  end
  if summary.has_deprecation then
    parts[#parts + 1] = "deprecation"
  end
  if (summary.feat or 0) > 0 then
    parts[#parts + 1] = "feat:" .. tostring(summary.feat)
  end
  if (summary.fix or 0) > 0 then
    parts[#parts + 1] = "fix:" .. tostring(summary.fix)
  end
  if (summary.refactor or 0) > 0 then
    parts[#parts + 1] = "refactor:" .. tostring(summary.refactor)
  end
  if (summary.perf or 0) > 0 then
    parts[#parts + 1] = "perf:" .. tostring(summary.perf)
  end
  if (summary.docs or 0) > 0 then
    parts[#parts + 1] = "docs:" .. tostring(summary.docs)
  end
  if (summary.chore or 0) > 0 then
    parts[#parts + 1] = "chore:" .. tostring(summary.chore)
  end
  if #parts == 0 then
    return "none"
  end
  return table.concat(parts, ", ")
end

local function parse_source_coordinates(src)
  if type(src) ~= "string" or src == "" then
    return nil
  end

  local normalized = vim.trim(src):gsub("/+$", "")
  local host, owner, repo = normalized:match("^https?://([^/]+)/([^/]+)/([^/]+)%.git$")
  if not host then
    host, owner, repo = normalized:match("^https?://([^/]+)/([^/]+)/([^/]+)$")
  end
  if not host then
    host, owner, repo = normalized:match("^git@([^:]+):([^/]+)/([^/]+)%.git$")
  end
  if not host then
    host, owner, repo = normalized:match("^git@([^:]+):([^/]+)/([^/]+)$")
  end
  if not host then
    host, owner, repo = normalized:match("^ssh://git@([^/]+)/([^/]+)/([^/]+)%.git$")
  end
  if not host then
    host, owner, repo = normalized:match("^ssh://git@([^/]+)/([^/]+)/([^/]+)$")
  end
  if not host or not owner or not repo then
    return nil
  end

  repo = repo:gsub("%.git$", "")
  return host, owner, repo
end

local function source_to_compare_url(src, rev_before, rev_after)
  if type(src) ~= "string" or src == "" or type(rev_before) ~= "string" or type(rev_after) ~= "string" then
    return nil
  end

  local host, owner, repo = parse_source_coordinates(src)
  if not host or not owner or not repo then
    return nil
  end

  if host == "github.com" or host == "codeberg.org" then
    return ("https://%s/%s/%s/compare/%s...%s"):format(host, owner, repo, rev_before, rev_after)
  end
  return nil
end

local function source_to_repo_url(src)
  if type(src) ~= "string" or src == "" then
    return nil
  end

  local host, owner, repo = parse_source_coordinates(src)
  if not host or not owner or not repo then
    return nil
  end
  return ("https://%s/%s/%s"):format(host, owner, repo)
end

local function repo_to_compare_url(repo_url, from_ref, to_ref)
  if type(repo_url) ~= "string" or repo_url == "" then
    return nil
  end
  if type(from_ref) ~= "string" or from_ref == "" or type(to_ref) ~= "string" or to_ref == "" then
    return nil
  end

  local host, owner, repo = repo_url:match("^https://([^/]+)/([^/]+)/([^/]+)$")
  if not host or not owner or not repo then
    return nil
  end
  if host == "github.com" or host == "codeberg.org" then
    return ("%s/compare/%s...%s"):format(repo_url, from_ref, to_ref)
  end
  return nil
end

local function short_rev(rev)
  if type(rev) ~= "string" or rev == "" then
    return nil
  end
  return rev:sub(1, 8)
end

local function infer_breaking_status(p_data)
  if p_data.status ~= "update" then
    return nil
  end

  local before_version = p_data.current_version or tag_on_revision(p_data.path, p_data.rev_before)
  local after_version = p_data.target_version or tag_on_revision(p_data.path, p_data.rev_after)
  p_data.current_version = before_version
  p_data.target_version = after_version

  local semver_change = semver_delta(before_version, after_version)
  p_data.semver_delta = semver_change

  local range_messages = commit_messages_between(p_data.path, p_data.rev_before, p_data.rev_after)
  local message_text = (type(range_messages) == "string" and range_messages ~= "") and range_messages
    or (p_data.pending_updates or "")

  local message_summary = classify_commit_signals(message_text)
  p_data.commit_signal = format_commit_signals(message_summary)

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

local function parse_pack_report_buffer(bufnr, merge)
  if not bufnr or not vim.api.nvim_buf_is_valid(bufnr) then
    return
  end

  local lines = vim.api.nvim_buf_get_lines(bufnr, 0, -1, false)
  if #lines == 0 then
    return
  end

  local current_group = nil
  local current_plugin = nil
  local plugins = {}
  local counts = { update = 0, same = 0, error = 0 }

  for _, line in ipairs(lines) do
    local section = line:match("^#%s+(%u%l+)")
    if section then
      local normalized = section:lower()
      if normalized == "update" or normalized == "same" or normalized == "error" then
        current_group = normalized
      else
        current_group = nil
      end
      current_plugin = nil
    elseif current_group then
      local name = line:match("^##%s+(.+)$")
      if name then
        name = vim.trim(name:gsub("%s*%(.+%)$", ""))
        current_plugin = {
          status = current_group,
          pending_lines = {},
        }
        plugins[name] = current_plugin
        if counts[current_group] ~= nil then
          counts[current_group] = counts[current_group] + 1
        end
      elseif current_plugin then
        local path = line:match("^Path:%s+(.+)$")
        if path then
          current_plugin.path = vim.trim(path)
        end

        local source = line:match("^Source:%s+(.+)$")
        if source then
          current_plugin.source = vim.trim(source)
        end

        local rev_before = line:match("^Revision before:%s+([0-9a-fA-F]+)")
        if rev_before then
          current_plugin.rev_before = rev_before
        end

        local rev_after_line = line:match("^Revision after:%s+(.+)$")
        if rev_after_line then
          current_plugin.rev_after = rev_after_line:match("^([0-9a-fA-F]+)") or current_plugin.rev_after
          current_plugin.target_version = rev_after_line:match("%(([^)]+)%)")
        end

        local rev_line = line:match("^Revision:%s+(.+)$")
        if rev_line then
          current_plugin.rev = rev_line:match("^([0-9a-fA-F]+)") or current_plugin.rev
          current_plugin.current_version = rev_line:match("%(([^)]+)%)")
        end

        if line:match("^Pending updates:%s*$") then
          current_plugin.collect_pending = true
        elseif current_plugin.collect_pending then
          if
            line:match("^#%s+")
            or line:match("^##%s+")
            or line:match("^Path:%s+")
            or line:match("^Source:%s+")
            or line:match("^Revision%s+")
          then
            current_plugin.collect_pending = false
          elseif line ~= "" then
            current_plugin.pending_lines[#current_plugin.pending_lines + 1] = line
          end
        end
      end
    end
  end

  for _, p_data in pairs(plugins) do
    p_data.pending_updates = table.concat(p_data.pending_lines or {}, "\n")
    p_data.breaking = infer_breaking_status(p_data)
    p_data.diff_url = source_to_compare_url(p_data.source, p_data.rev_before, p_data.rev_after)
    p_data.pending_lines = nil
    p_data.collect_pending = nil
  end

  if merge then
    local merged = vim.deepcopy(pack_report_cache.plugins or {})
    for name, data in pairs(plugins) do
      merged[name] = data
    end
    pack_report_cache.plugins = merged
  else
    pack_report_cache.plugins = plugins
  end
  pack_report_cache.updated_at = os.time()
  write_persisted_state()
  return counts
end

local function find_pack_report_buffer()
  local current = vim.api.nvim_get_current_buf()
  local current_name = vim.api.nvim_buf_get_name(current)
  if current_name:match("^nvim%-pack://confirm#") then
    return current
  end

  local matched = nil
  for _, bufnr in ipairs(vim.api.nvim_list_bufs()) do
    if vim.api.nvim_buf_is_valid(bufnr) then
      local name = vim.api.nvim_buf_get_name(bufnr)
      if name:match("^nvim%-pack://confirm#") then
        matched = bufnr
      end
    end
  end

  return matched
end

local function refresh_pack_report_cache_from_report_buffer(merge)
  local bufnr = find_pack_report_buffer()
  if bufnr then
    return parse_pack_report_buffer(bufnr, merge), bufnr
  end
  return nil, nil
end

local function scan_updates_to_cache(online, names, merge, opts)
  opts = opts or {}
  vim.pack.update(names, online and nil or { offline = true })
  local counts, report_bufnr = refresh_pack_report_cache_from_report_buffer(merge)
  if not counts then
    notify_err("Failed to capture vim.pack report buffer")
    return false
  end
  if opts.record_counts ~= false then
    pack_report_cache.last_check_counts = counts
  end
  pack_report_cache.mode = online and "online" or "offline"
  if online and opts.mark_online then
    pack_report_cache.last_online_at = os.time()
  elseif (not online) and opts.mark_offline then
    pack_report_cache.last_offline_at = os.time()
  end
  write_persisted_state()
  if report_bufnr and vim.api.nvim_buf_is_valid(report_bufnr) then
    pcall(vim.api.nvim_buf_delete, report_bufnr, { force = true })
  end
  return true
end

local function ensure_dashboard_cache(online, force_scan)
  if force_scan then
    -- Explicit force refresh should count as a real online/offline check.
    return scan_updates_to_cache(online, nil, false, { mark_online = online, mark_offline = not online })
  end
  if type(pack_report_cache.plugins) == "table" and next(pack_report_cache.plugins) ~= nil then
    return true
  end

  -- Default behavior: no implicit network check on dashboard open.
  -- Use `r`/`R`, `:PackSync`, or `:PackDashboard!` for explicit checks.
  if vim.g.pack_dashboard_autocheck_on_open == true then
    -- Optional opt-in: bootstrap cache without mutating explicit check stamps.
    return scan_updates_to_cache(online, nil, false, {
      mark_online = false,
      mark_offline = false,
      record_counts = false,
    })
  end

  return true
end

local function collect_dashboard_rows()
  local ok, plugins = pcall(vim.pack.get, nil, { info = false })
  if not ok then
    notify_err("Failed to read vim.pack plugins")
    return {}
  end

  local rows = {}
  for _, plugin in ipairs(plugins) do
    local name = plugin.spec.name
    local p_data = pack_report_cache.plugins[name] or {}
    local status = p_data.status or "unknown"
    local source = p_data.source or plugin.spec.src
    local diff_url = p_data.diff_url or source_to_compare_url(source, p_data.rev_before, p_data.rev_after)
    local breaking = p_data.breaking
    if breaking == nil and status == "update" then
      p_data.source = source
      p_data.diff_url = diff_url
      p_data.breaking = infer_breaking_status(p_data)
      breaking = p_data.breaking
    end

    rows[#rows + 1] = {
      name = name,
      status = status,
      source = source,
      rev = plugin.rev,
      target_version = p_data.target_version,
      current_version = p_data.current_version,
      rev_before = p_data.rev_before,
      rev_after = p_data.rev_after,
      pending_updates = p_data.pending_updates,
      breaking = breaking,
      semver_delta = p_data.semver_delta,
      commit_signal = p_data.commit_signal,
      risk_reason = p_data.risk_reason,
      diff_url = diff_url,
      repo_url = source_to_repo_url(source),
    }
  end

  for _, row in ipairs(rows) do
    if not row.diff_url and row.status == "update" and row.repo_url then
      local from_ref = row.current_version or row.rev_before
      local to_ref = row.target_version or row.rev_after
      row.diff_url = repo_to_compare_url(row.repo_url, from_ref, to_ref)
    end
  end

  return rows
end

local function open_pack_dashboard(online, force_scan)
  if not ensure_dashboard_cache(online, force_scan) then
    return
  end

  local use_nerd_font = vim.g.pack_dashboard_ascii ~= true
  local fast_scroll_mode = vim.g.pack_dashboard_fast_scroll ~= false
  local icons = use_nerd_font
      and {
        update = "",
        same = "",
        error = "",
        unknown = "",
        risk_break = "!",
        risk_safe = "+",
        risk_unknown = "-",
        link_diff = "diff",
        link_repo = "repo",
      }
    or {
      update = "U",
      same = "=",
      error = "!",
      unknown = "?",
      risk_break = "!",
      risk_safe = "+",
      risk_unknown = "-",
      link_diff = "diff",
      link_repo = "repo",
    }
  local status_icon = {
    update = icons.update,
    same = icons.same,
    error = icons.error,
    unknown = icons.unknown,
  }
  local status_rank = { update = 1, error = 2, same = 3, unknown = 4 }
  local filter_modes = { "all", "updates", "issues", "selected" }
  local rows = collect_dashboard_rows()
  local selected = {}
  for _, name in ipairs(dashboard_ui_cache.selected_names or {}) do
    selected[name] = true
  end
  local row_by_line = {}
  local first_data_line = 1
  local filter_mode = dashboard_ui_cache.filter_mode or "all"
  local sort_mode = dashboard_ui_cache.sort_mode or "status"
  local search_text = dashboard_ui_cache.search_text
  local winid
  local details_winid
  local details_bufnr

  local bufnr = vim.api.nvim_create_buf(false, true)
  vim.bo[bufnr].buftype = "nofile"
  vim.bo[bufnr].bufhidden = "wipe"
  vim.bo[bufnr].buflisted = false
  vim.bo[bufnr].swapfile = false
  vim.bo[bufnr].modifiable = true
  vim.bo[bufnr].filetype = "packdashboard"

  local function open_popup_window()
    local total_lines = vim.o.lines - vim.o.cmdheight
    local width_ratio = tonumber(vim.g.pack_dashboard_width_ratio) or 0.68
    local height_ratio = tonumber(vim.g.pack_dashboard_height_ratio) or 0.68
    local min_width = tonumber(vim.g.pack_dashboard_min_width) or 84
    local min_height = tonumber(vim.g.pack_dashboard_min_height) or 18
    local margin = tonumber(vim.g.pack_dashboard_margin) or 6

    width_ratio = math.max(0.45, math.min(0.98, width_ratio))
    height_ratio = math.max(0.45, math.min(0.98, height_ratio))
    margin = math.max(2, margin)

    local width = math.min(math.max(min_width, math.floor(vim.o.columns * width_ratio)), vim.o.columns - margin)
    local height = math.min(math.max(min_height, math.floor(total_lines * height_ratio)), total_lines - margin)
    local row = math.floor((total_lines - height) / 2)
    local col = math.floor((vim.o.columns - width) / 2)

    winid = vim.api.nvim_open_win(bufnr, true, {
      relative = "editor",
      style = "minimal",
      border = "rounded",
      title = " vim.pack dashboard ",
      title_pos = "center",
      row = row,
      col = col,
      width = width,
      height = height,
    })

    vim.wo[winid].number = false
    vim.wo[winid].relativenumber = false
    vim.wo[winid].signcolumn = "no"
    vim.wo[winid].foldcolumn = "0"
    vim.wo[winid].wrap = false
    vim.wo[winid].cursorline = false
    vim.wo[winid].smoothscroll = false
  end

  local function close_details_popup()
    if details_winid and vim.api.nvim_win_is_valid(details_winid) then
      pcall(vim.api.nvim_win_close, details_winid, true)
    end
    if details_bufnr and vim.api.nvim_buf_is_valid(details_bufnr) then
      pcall(vim.api.nvim_buf_delete, details_bufnr, { force = true })
    end
    details_winid = nil
    details_bufnr = nil
  end

  local function risk_label(row)
    if row.status ~= "update" then
      return "-"
    end
    if row.breaking == true then
      return icons.risk_break
    end
    if row.breaking == false then
      return icons.risk_safe
    end
    return icons.risk_unknown
  end

  local function links_cell(row)
    local has_diff = row.diff_url ~= nil
    local has_repo = row.repo_url ~= nil

    -- Compact availability indicators: prefer diff, then repo fallback.
    if has_diff then
      return icons.link_diff
    end
    if has_repo then
      return icons.link_repo
    end
    return "-"
  end

  local function truncate_display(text, max_width)
    if type(text) ~= "string" then
      text = tostring(text or "")
    end
    if max_width <= 0 then
      return ""
    end
    if vim.fn.strdisplaywidth(text) <= max_width then
      return text
    end

    local ellipsis = "…"
    if max_width == 1 then
      return ellipsis
    end

    local out = ""
    for _, ch in ipairs(vim.fn.split(text, "\\zs")) do
      local candidate = out .. ch
      if vim.fn.strdisplaywidth(candidate .. ellipsis) > max_width then
        break
      end
      out = candidate
    end

    return out .. ellipsis
  end

  local function pad_cell(text, width)
    local value = truncate_display(text, width)
    local pad = width - vim.fn.strdisplaywidth(value)
    if pad <= 0 then
      return value
    end
    return value .. string.rep(" ", pad)
  end

  local function cycle_filter_mode()
    for i, mode in ipairs(filter_modes) do
      if mode == filter_mode then
        filter_mode = filter_modes[(i % #filter_modes) + 1]
        return
      end
    end
    filter_mode = filter_modes[1]
  end

  local function visible_rows()
    local out = {}
    for _, row in ipairs(rows) do
      local include = true
      if filter_mode == "updates" then
        include = row.status == "update"
      elseif filter_mode == "issues" then
        include = row.status == "update" or row.status == "error"
      elseif filter_mode == "selected" then
        include = selected[row.name] == true
      end

      if include and search_text and search_text ~= "" then
        include = row.name:lower():find(search_text:lower(), 1, true) ~= nil
      end

      if include then
        out[#out + 1] = row
      end
    end

    if sort_mode == "name" then
      table.sort(out, function(a, b)
        return a.name < b.name
      end)
    else
      table.sort(out, function(a, b)
        local ra = status_rank[a.status] or status_rank.unknown
        local rb = status_rank[b.status] or status_rank.unknown
        if ra ~= rb then
          return ra < rb
        end
        return a.name < b.name
      end)
    end

    return out
  end

  local function summary_counts()
    local counts = { update = 0, same = 0, error = 0, unknown = 0, breaking = 0 }
    for _, row in ipairs(rows) do
      counts[row.status] = (counts[row.status] or 0) + 1
      if row.breaking == true then
        counts.breaking = counts.breaking + 1
      end
    end
    return counts
  end

  local function selected_count(visible_only)
    local count = 0
    local scope = visible_only and visible_rows() or rows
    for _, row in ipairs(scope) do
      if selected[row.name] then
        count = count + 1
      end
    end
    return count
  end

  local function selected_names(visible_only)
    local names = {}
    local scope = visible_only and visible_rows() or rows
    for _, row in ipairs(scope) do
      if selected[row.name] then
        names[#names + 1] = row.name
      end
    end
    return names
  end

  local function persist_dashboard_ui_state()
    local selected_names_out = {}
    for name, enabled in pairs(selected) do
      if enabled == true then
        selected_names_out[#selected_names_out + 1] = name
      end
    end
    table.sort(selected_names_out)
    dashboard_ui_cache.filter_mode =
      normalize_mode(filter_mode, { all = true, updates = true, issues = true, selected = true }, "all")
    dashboard_ui_cache.sort_mode = normalize_mode(sort_mode, { status = true, name = true }, "status")
    dashboard_ui_cache.search_text = (type(search_text) == "string" and search_text ~= "") and search_text or nil
    dashboard_ui_cache.selected_names = selected_names_out
    write_persisted_state()
  end

  local function version_cell(row)
    local current = row.current_version or short_rev(row.rev_before) or short_rev(row.rev)
    local target = row.target_version or short_rev(row.rev_after)
    if row.status == "update" then
      current = current or "-"
      target = target or "-"
      return current .. " -> " .. target
    end
    return current or "-"
  end

  local function open_details_popup(row)
    if not row then
      return
    end
    close_details_popup()

    local pending = row.pending_updates
    if type(pending) ~= "string" or pending == "" then
      pending = "(No pending update details available)"
    end

    local lines = {
      ("Plugin: %s"):format(row.name),
      ("Status: %s"):format(row.status),
      ("Risk:   %s"):format(risk_label(row)),
      ("Risk reason: %s"):format(row.risk_reason or "-"),
      ("Semver delta: %s"):format(row.semver_delta or "n/a"),
      ("Commit signals: %s"):format(row.commit_signal or "none"),
      ("Source: %s"):format(row.source or "-"),
      ("Repo:   %s"):format(row.repo_url or "-"),
      ("Diff:   %s"):format(row.diff_url or "-"),
      ("Current:%s"):format(" " .. (row.current_version or short_rev(row.rev_before) or short_rev(row.rev) or "-")),
      ("Target: %s"):format(row.target_version or short_rev(row.rev_after) or "-"),
      "",
      "Pending updates:",
    }
    vim.list_extend(lines, vim.split(pending, "\n", { trimempty = false }))

    local p_cache = pack_report_cache.plugins[row.name]
    local p_path = p_cache and p_cache.path
    if row.status == "update" and p_path and row.rev_before and row.rev_after then
      local subjects = commit_subjects_between(p_path, row.rev_before, row.rev_after)
      if subjects and #subjects > 0 then
        lines[#lines + 1] = ""
        local max_shown = 30
        local shown = math.min(#subjects, max_shown)
        lines[#lines + 1] = string.format("Changelog (%d commit%s):", #subjects, #subjects == 1 and "" or "s")
        for i = 1, shown do
          lines[#lines + 1] = "  " .. subjects[i]
        end
        if #subjects > max_shown then
          lines[#lines + 1] = string.format("  ... and %d more", #subjects - max_shown)
        end
      end
    end

    lines[#lines + 1] = ""
    lines[#lines + 1] = "q / <Esc> close | o open diff | O open repo"

    details_bufnr = vim.api.nvim_create_buf(false, true)
    vim.bo[details_bufnr].buftype = "nofile"
    vim.bo[details_bufnr].bufhidden = "wipe"
    vim.bo[details_bufnr].buflisted = false
    vim.bo[details_bufnr].swapfile = false
    vim.bo[details_bufnr].filetype = "markdown"
    vim.api.nvim_buf_set_lines(details_bufnr, 0, -1, false, lines)
    vim.bo[details_bufnr].modifiable = false

    local editor_w = vim.o.columns
    local editor_h = vim.o.lines - vim.o.cmdheight
    local width = math.min(math.max(90, math.floor(editor_w * 0.75)), editor_w - 4)
    local height = math.min(math.max(22, math.floor(editor_h * 0.70)), editor_h - 4)
    local row_pos = math.floor((editor_h - height) / 2)
    local col_pos = math.floor((editor_w - width) / 2)

    details_winid = vim.api.nvim_open_win(details_bufnr, true, {
      relative = "editor",
      style = "minimal",
      border = "rounded",
      title = (" %s details "):format(row.name),
      title_pos = "center",
      row = row_pos,
      col = col_pos,
      width = width,
      height = height,
    })
    vim.wo[details_winid].wrap = true

    vim.keymap.set("n", "q", close_details_popup, { buffer = details_bufnr, nowait = true, silent = true })
    vim.keymap.set("n", "<Esc>", close_details_popup, { buffer = details_bufnr, nowait = true, silent = true })
    vim.keymap.set("n", "o", function()
      if row.diff_url then
        vim.ui.open(row.diff_url)
      else
        vim.notify("No diff URL for this plugin", vim.log.levels.WARN)
      end
    end, { buffer = details_bufnr, nowait = true, silent = true })
    vim.keymap.set("n", "O", function()
      if row.repo_url then
        vim.ui.open(row.repo_url)
      else
        vim.notify("No repo URL for this plugin", vim.log.levels.WARN)
      end
    end, { buffer = details_bufnr, nowait = true, silent = true })
  end

  local function render()
    ensure_dashboard_highlights()
    local mode = pack_report_cache.mode or "unknown"
    local counts = summary_counts()
    local visible = visible_rows()
    local sel_visible = selected_count(true)
    local sel_total = selected_count(false)
    local checked_stamp = pack_report_cache.updated_at and os.date("%H:%M:%S", pack_report_cache.updated_at) or "never"
    local applied_stamp = pack_report_cache.last_applied_at and os.date("%H:%M:%S", pack_report_cache.last_applied_at)
      or "never"
    local applied_count = tonumber(pack_report_cache.last_applied_count) or 0
    local raw = pack_report_cache.last_check_counts
    local raw_line = "last-check raw: n/a (run r or :PackSync)"
    if type(raw) == "table" then
      raw_line = string.format(
        "last-check raw: update:%d same:%d error:%d",
        tonumber(raw.update) or 0,
        tonumber(raw.same) or 0,
        tonumber(raw.error) or 0
      )
    end
    local win_width = (winid and vim.api.nvim_win_is_valid(winid)) and vim.api.nvim_win_get_width(winid)
      or vim.o.columns
    local row_width = math.max(80, win_width - 2)
    local sep_char = use_nerd_font and "─" or "-"
    local sep = string.rep(sep_char, row_width)

    local title = use_nerd_font and "󰒲  vim.pack dashboard" or "vim.pack dashboard"
    local title_line = string.format(
      "%s   mode:%s   checked:%s   applied:%s (%d)   selected:%d/%d",
      title,
      mode,
      checked_stamp,
      applied_stamp,
      applied_count,
      sel_visible,
      sel_total
    )
    local stats_line
    if use_nerd_font then
      stats_line = string.format(
        "%s %d   %s %d   %s %d   %s %d   %s %d",
        icons.update,
        counts.update,
        icons.same,
        counts.same,
        icons.error,
        counts.error,
        icons.unknown,
        counts.unknown,
        icons.risk_break,
        counts.breaking
      )
    else
      stats_line = string.format(
        "updates:%d  same:%d  errors:%d  unknown:%d  breaking:%d",
        counts.update,
        counts.same,
        counts.error,
        counts.unknown,
        counts.breaking
      )
    end
    local controls_line = string.format(
      "r/R refresh  <CR>/u/U update  f filter:%s  s sort:%s  / search:%s  a select-all  o link  K details  ? help",
      filter_mode,
      sort_mode,
      search_text or "-"
    )

    local name_col = 34
    local version_col = 26
    local links_col = 12
    local header_row = table.concat({
      pad_cell("SEL", 3),
      pad_cell("ST", 2),
      pad_cell("RK", 2),
      pad_cell("PLUGIN", name_col),
      pad_cell("VERSION", version_col),
      pad_cell("LINKS", links_col),
    }, " ")

    local lines = {
      title_line,
      stats_line,
      raw_line,
      controls_line,
      sep,
      header_row,
      sep,
    }

    row_by_line = {}
    first_data_line = #lines + 1
    for _, row in ipairs(visible) do
      local sel = selected[row.name] and "[x]" or "[ ]"
      local icon = status_icon[row.status] or "?"
      local risk = risk_label(row)
      lines[#lines + 1] = table.concat({
        pad_cell(sel, 3),
        pad_cell(icon, 2),
        pad_cell(risk, 2),
        pad_cell(row.name, name_col),
        pad_cell(version_cell(row), version_col),
        pad_cell(links_cell(row), links_col),
      }, " ")
      row_by_line[#lines] = row
    end
    if #visible == 0 then
      lines[#lines + 1] = "(No plugins match current filter/search)"
    end

    vim.bo[bufnr].modifiable = true
    vim.api.nvim_buf_set_lines(bufnr, 0, -1, false, lines)
    vim.bo[bufnr].modifiable = false

    vim.api.nvim_buf_clear_namespace(bufnr, dashboard_ns, 0, -1)
    local function hl_line(line_no, group)
      if line_no > 0 and line_no <= #lines then
        pcall(vim.api.nvim_buf_set_extmark, bufnr, dashboard_ns, line_no - 1, 0, {
          hl_group = group,
          end_col = #lines[line_no],
        })
      end
    end
    hl_line(1, "PackDashboardTitle")
    hl_line(2, "PackDashboardStats")
    hl_line(3, "PackDashboardMeta")
    hl_line(4, "PackDashboardMeta")
    hl_line(5, "PackDashboardMeta")
    hl_line(6, "PackDashboardHeader")
    hl_line(7, "PackDashboardMeta")

    local status_hl = {
      update = "PackDashboardStatusUpdate",
      same = "PackDashboardStatusSame",
      error = "PackDashboardStatusError",
      unknown = "PackDashboardStatusUnknown",
    }

    local row_count = 0
    for _ in pairs(row_by_line) do
      row_count = row_count + 1
    end

    -- Keep scrolling smooth on large plugin sets by trimming per-row decorations.
    local allow_row_highlights = not fast_scroll_mode or row_count <= 120
    if not allow_row_highlights then
      return
    end

    -- Row layout uses fixed-width columns. These byte offsets are stable:
    -- 0..2 = [ ]/[x], 4..5 = status, 7..8 = risk.
    local sel_start, sel_end = 0, 3
    local st_start, st_end = 4, 6
    local rk_start, rk_end = 7, 9

    for line_no, row in pairs(row_by_line) do
      if selected[row.name] then
        pcall(vim.api.nvim_buf_set_extmark, bufnr, dashboard_ns, line_no - 1, sel_start, {
          hl_group = "PackDashboardSelected",
          end_col = sel_end,
        })
      end

      pcall(vim.api.nvim_buf_set_extmark, bufnr, dashboard_ns, line_no - 1, st_start, {
        hl_group = status_hl[row.status] or "PackDashboardStatusUnknown",
        end_col = st_end,
      })

      local risk_group = "PackDashboardRiskUnknown"
      if row.breaking == true then
        risk_group = "PackDashboardRiskBreak"
      elseif row.breaking == false then
        risk_group = "PackDashboardRiskSafe"
      end
      if row.status == "update" then
        pcall(vim.api.nvim_buf_set_extmark, bufnr, dashboard_ns, line_no - 1, rk_start, {
          hl_group = risk_group,
          end_col = rk_end,
        })
      end
    end
  end

  local function row_at_cursor()
    local line = vim.api.nvim_win_get_cursor(0)[1]
    return row_by_line[line]
  end

  local function refresh(next_online, names, merge, opts)
    if scan_updates_to_cache(next_online, names, merge, opts) then
      local current = row_at_cursor()
      local current_name = current and current.name or nil
      rows = collect_dashboard_rows()
      local previous_selected = selected
      selected = {}
      for _, row in ipairs(rows) do
        if previous_selected[row.name] then
          selected[row.name] = true
        end
      end
      if winid and vim.api.nvim_win_is_valid(winid) then
        vim.api.nvim_set_current_win(winid)
      end
      render()
      persist_dashboard_ui_state()
      if current_name then
        for line, row in pairs(row_by_line) do
          if row.name == current_name then
            pcall(vim.api.nvim_win_set_cursor, 0, { line, 0 })
            break
          end
        end
      end
    end
  end

  local function update_by_names(names, empty_msg, noop_msg)
    if #names == 0 then
      vim.notify(empty_msg or "No plugins selected", vim.log.levels.WARN)
      return
    end

    local filtered = {}
    local seen = {}
    for _, name in ipairs(names) do
      if type(name) == "string" and name ~= "" and not seen[name] then
        seen[name] = true
        filtered[#filtered + 1] = name
      end
    end

    if #filtered == 0 then
      vim.notify(noop_msg or "Selected plugins are already up to date", vim.log.levels.INFO)
      return
    end

    vim.pack.update(filtered, { force = true })
    pack_report_cache.last_applied_at = os.time()
    pack_report_cache.last_applied_count = #filtered
    write_persisted_state()
    pcall(refresh_version_policy_if_needed)
    refresh(false, filtered, true, { mark_online = false, mark_offline = false, record_counts = false })
  end

  local function close_dashboard()
    close_details_popup()
    if winid and vim.api.nvim_win_is_valid(winid) then
      pcall(vim.api.nvim_win_close, winid, true)
    else
      pcall(vim.api.nvim_buf_delete, bufnr, { force = true })
    end
  end

  vim.keymap.set("n", "q", close_dashboard, { buffer = bufnr, nowait = true, silent = true })
  vim.keymap.set("n", "<Esc>", close_dashboard, { buffer = bufnr, nowait = true, silent = true })
  vim.keymap.set("n", "gg", function()
    if next(row_by_line) == nil then
      return
    end
    pcall(vim.api.nvim_win_set_cursor, 0, { first_data_line, 0 })
  end, { buffer = bufnr, nowait = true, silent = true })
  vim.keymap.set("n", "r", function()
    refresh(true, nil, nil, { mark_online = true, mark_offline = false })
  end, { buffer = bufnr, nowait = true, silent = true })
  vim.keymap.set("n", "R", function()
    refresh(false, nil, nil, { mark_online = false, mark_offline = true })
  end, { buffer = bufnr, nowait = true, silent = true })

  vim.keymap.set("n", "<Space>", function()
    local row = row_at_cursor()
    if not row then
      return
    end
    selected[row.name] = not selected[row.name]
    render()
    persist_dashboard_ui_state()
  end, { buffer = bufnr, nowait = true, silent = true })

  vim.keymap.set("n", "x", function()
    local row = row_at_cursor()
    if not row then
      return
    end
    selected[row.name] = not selected[row.name]
    render()
    persist_dashboard_ui_state()
  end, { buffer = bufnr, nowait = true, silent = true })

  local function visual_toggle_selection()
    local start_line = vim.fn.line("v")
    local end_line = vim.fn.line(".")
    if start_line > end_line then
      start_line, end_line = end_line, start_line
    end
    local toggled = false
    for line = start_line, end_line do
      local row = row_by_line[line]
      if row then
        selected[row.name] = not selected[row.name]
        toggled = true
      end
    end
    vim.api.nvim_feedkeys(vim.api.nvim_replace_termcodes("<Esc>", true, false, true), "nx", false)
    if toggled then
      render()
      persist_dashboard_ui_state()
    end
  end

  vim.keymap.set("v", "<Space>", visual_toggle_selection, { buffer = bufnr, nowait = true, silent = true })
  vim.keymap.set("v", "x", visual_toggle_selection, { buffer = bufnr, nowait = true, silent = true })

  vim.keymap.set("n", "a", function()
    local visible = visible_rows()
    for _, row in ipairs(visible) do
      selected[row.name] = true
    end
    render()
    persist_dashboard_ui_state()
  end, { buffer = bufnr, nowait = true, silent = true })

  vim.keymap.set("n", "A", function()
    selected = {}
    render()
    persist_dashboard_ui_state()
  end, { buffer = bufnr, nowait = true, silent = true })

  vim.keymap.set("n", "<CR>", function()
    local row = row_at_cursor()
    if not row then
      return
    end
    update_by_names({ row.name }, "No plugin on current row", "Plugin is already up to date")
  end, { buffer = bufnr, nowait = true, silent = true })

  vim.keymap.set("n", "u", function()
    local names = selected_names(true)
    if #names == 0 then
      local current = row_at_cursor()
      if current then
        names = { current.name }
      end
    end
    update_by_names(names, "No selected plugins", "Selected plugins are already up to date")
  end, { buffer = bufnr, nowait = true, silent = true })

  vim.keymap.set("n", "U", function()
    local names = {}
    for _, row in ipairs(visible_rows()) do
      names[#names + 1] = row.name
    end
    update_by_names(names, "No visible plugins to update", "All visible plugins are already up to date")
  end, { buffer = bufnr, nowait = true, silent = true })

  local function open_diff_or_repo_for_row(row)
    if not row then
      return
    end
    if row.diff_url then
      vim.ui.open(row.diff_url)
      return
    end
    if row.repo_url then
      vim.notify("No direct compare URL; opening repository instead", vim.log.levels.INFO)
      vim.ui.open(row.repo_url)
      return
    end
    vim.notify("No diff/repo URL for this plugin", vim.log.levels.WARN)
  end

  vim.keymap.set("n", "o", function()
    local row = row_at_cursor()
    open_diff_or_repo_for_row(row)
  end, { buffer = bufnr, nowait = true, silent = true })

  vim.keymap.set("n", "O", function()
    local row = row_at_cursor()
    if not row or not row.repo_url then
      vim.notify("No repo URL for this plugin", vim.log.levels.WARN)
      return
    end
    vim.ui.open(row.repo_url)
  end, { buffer = bufnr, nowait = true, silent = true })

  vim.keymap.set("n", "K", function()
    local row = row_at_cursor()
    if not row then
      return
    end
    open_details_popup(row)
  end, { buffer = bufnr, nowait = true, silent = true })

  vim.keymap.set("n", "T", function()
    local row = row_at_cursor()
    if row and row.name then
      vim.api.nvim_cmd({ cmd = "PackTrace", args = { row.name } }, {})
      return
    end
    vim.api.nvim_cmd({ cmd = "PackTrace" }, {})
  end, { buffer = bufnr, nowait = true, silent = true })

  vim.keymap.set("n", "f", function()
    cycle_filter_mode()
    render()
    persist_dashboard_ui_state()
  end, { buffer = bufnr, nowait = true, silent = true })

  vim.keymap.set("n", "s", function()
    sort_mode = sort_mode == "status" and "name" or "status"
    render()
    persist_dashboard_ui_state()
  end, { buffer = bufnr, nowait = true, silent = true })

  vim.keymap.set("n", "/", function()
    vim.ui.input({
      prompt = "Plugin search (name substring): ",
      default = search_text or "",
    }, function(input)
      if input == nil then
        return
      end
      local normalized = vim.trim(input)
      search_text = normalized ~= "" and normalized or nil
      if winid and vim.api.nvim_win_is_valid(winid) then
        vim.api.nvim_set_current_win(winid)
      end
      render()
      persist_dashboard_ui_state()
    end)
  end, { buffer = bufnr, nowait = true, silent = true })

  vim.keymap.set("n", "c", function()
    search_text = nil
    render()
    persist_dashboard_ui_state()
  end, { buffer = bufnr, nowait = true, silent = true })

  vim.keymap.set("n", "?", function()
    local help_lines = {
      "vim.pack dashboard keys",
      "",
      "q / <Esc>  close dashboard",
      "r / R      refresh online / offline",
      "f          cycle filter (all -> updates -> issues -> selected)",
      "s          cycle sort (status <-> name)",
      "/ / c      set search / clear search",
      "<Space>/x  toggle row selection (also works in visual mode)",
      "a / A      select all visible / clear all selection",
      "<CR>       update plugin at cursor",
      "u / U      update selected (or cursor if none) / update all listed",
      "o          open diff URL (fallback: repository)",
      "O          open repository URL",
      "K          open details popup",
      "T          open load trace (current plugin)",
    }
    local hbuf = vim.api.nvim_create_buf(false, true)
    vim.bo[hbuf].buftype = "nofile"
    vim.bo[hbuf].bufhidden = "wipe"
    vim.bo[hbuf].swapfile = false
    vim.api.nvim_buf_set_lines(hbuf, 0, -1, false, help_lines)
    vim.bo[hbuf].modifiable = false

    local editor_w = vim.o.columns
    local editor_h = vim.o.lines - vim.o.cmdheight
    local width = math.min(88, editor_w - 4)
    local height = math.min(#help_lines + 2, editor_h - 4)
    local hwin = vim.api.nvim_open_win(hbuf, true, {
      relative = "editor",
      style = "minimal",
      border = "rounded",
      title = " dashboard help ",
      title_pos = "center",
      row = math.floor((editor_h - height) / 2),
      col = math.floor((editor_w - width) / 2),
      width = width,
      height = height,
    })
    vim.keymap.set("n", "q", function()
      if hwin and vim.api.nvim_win_is_valid(hwin) then
        vim.api.nvim_win_close(hwin, true)
      end
    end, { buffer = hbuf, nowait = true, silent = true })
    vim.keymap.set("n", "<Esc>", function()
      if hwin and vim.api.nvim_win_is_valid(hwin) then
        vim.api.nvim_win_close(hwin, true)
      end
    end, { buffer = hbuf, nowait = true, silent = true })
  end, { buffer = bufnr, nowait = true, silent = true })

  open_popup_window()
  render()
end

function M.setup()
  if configured then
    return
  end
  configured = true
  load_persisted_state_once()

  vim.api.nvim_create_user_command("PackSync", function()
    vim.pack.update()
    local counts = refresh_pack_report_cache_from_report_buffer()
    if counts then
      pack_report_cache.last_check_counts = counts
    end
    pack_report_cache.mode = "online"
    pack_report_cache.last_online_at = os.time()
    write_persisted_state()
    pcall(refresh_version_policy_if_needed)
  end, {
    desc = "Check updates online (fetch remotes)",
  })

  vim.api.nvim_create_user_command("PackStatus", function()
    vim.pack.update(nil, { offline = true })
    local counts = refresh_pack_report_cache_from_report_buffer()
    if counts then
      pack_report_cache.last_check_counts = counts
    end
    pack_report_cache.mode = "offline"
    pack_report_cache.last_offline_at = os.time()
    write_persisted_state()
    pcall(refresh_version_policy_if_needed)
  end, {
    desc = "Show status from local refs only (offline)",
  })

  vim.api.nvim_create_user_command("PackDashboardStats", function()
    local raw = pack_report_cache.last_check_counts
    local raw_text = "update:n/a same:n/a error:n/a"
    if type(raw) == "table" then
      raw_text = string.format(
        "update:%d same:%d error:%d",
        tonumber(raw.update) or 0,
        tonumber(raw.same) or 0,
        tonumber(raw.error) or 0
      )
    end
    local checked = pack_report_cache.updated_at and os.date("%H:%M:%S", pack_report_cache.updated_at) or "never"
    local applied = pack_report_cache.last_applied_at and os.date("%H:%M:%S", pack_report_cache.last_applied_at)
      or "never"
    local applied_count = tonumber(pack_report_cache.last_applied_count) or 0
    vim.notify(
      string.format(
        "PackDashboard last-check [%s] mode:%s checked:%s applied:%s (%d)",
        raw_text,
        pack_report_cache.mode or "unknown",
        checked,
        applied,
        applied_count
      ),
      vim.log.levels.INFO
    )
  end, {
    desc = "Show last raw vim.pack check counters",
  })

  vim.api.nvim_create_user_command("PackDashboard", function(cmd)
    open_pack_dashboard(true, cmd.bang)
  end, {
    bang = true,
    desc = "Open vim.pack dashboard with update risk and diff links",
  })

  vim.api.nvim_create_user_command("PackMenu", function(cmd)
    open_pack_dashboard(true, cmd.bang)
  end, {
    bang = true,
    desc = "Open vim.pack dashboard (legacy alias)",
  })
end

return M
