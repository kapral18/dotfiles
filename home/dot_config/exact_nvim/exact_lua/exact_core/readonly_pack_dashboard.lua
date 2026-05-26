local semver = require("core.pack.semver")

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

-- Module-level singleton refs so repeated `:PackDashboard` calls reuse the
-- same floating window instead of stacking multiple instances. Cleared by the
-- `WinClosed` autocmd registered in `open_pack_dashboard`.
local dashboard_winid = nil
local dashboard_online_check_running = false
local dashboard_online_check_progress = nil

-- Plugin names currently declared by `core.plugins.setup`. Populated at
-- startup via `M.set_declared_plugin_names`; any `vim.pack` entry without a
-- matching name is shown as an "orphan" row for manual cleanup (`C` key).
-- Left empty until set so that pre-setup dashboard access doesn't mis-classify
-- every plugin as orphaned.
local declared_names_cache = {}

local function persisted_state_path()
  return vim.fn.stdpath("state") .. "/pack_dashboard_state.json"
end

local policy = require("core.pack.policy")

local load_version_policy = policy.load_version_policy
local refresh_version_policy_if_needed = policy.refresh_version_policy_if_needed
local rebuild_version_policy = policy.rebuild_version_policy

-- Record the set of plugin names declared by the active plugin specs so the
-- dashboard can distinguish "managed" packs from on-disk orphans. Accepts
-- either an array of names or a set (`name = true`). Calling with `nil` or a
-- non-table resets the cache to empty (which disables orphan flagging).
function M.set_declared_plugin_names(names)
  if type(names) ~= "table" then
    declared_names_cache = {}
    return
  end
  local normalized = {}
  if vim.islist(names) then
    for _, n in ipairs(names) do
      if type(n) == "string" and n ~= "" then
        normalized[n] = true
      end
    end
  else
    for n, v in pairs(names) do
      if type(n) == "string" and n ~= "" and v then
        normalized[n] = true
      end
    end
  end
  declared_names_cache = normalized
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

local function format_cache_stamp(epoch)
  epoch = normalize_epoch(epoch)
  if not epoch then
    return "never"
  end

  local now = os.time()
  if os.date("%Y-%m-%d", epoch) == os.date("%Y-%m-%d", now) then
    return os.date("%H:%M:%S", epoch)
  end
  return os.date("%Y-%m-%d %H:%M", epoch)
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
  set_hl(0, "PackDashboardStatusOrphan", { default = true, link = "DiagnosticWarn" })
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

local function format_check_counts(counts)
  if type(counts) ~= "table" then
    return "update:n/a same:n/a error:n/a"
  end

  return string.format(
    "update:%d same:%d error:%d",
    tonumber(counts.update) or 0,
    tonumber(counts.same) or 0,
    tonumber(counts.error) or 0
  )
end

local function pending_update_names(limit)
  local plugins = pack_report_cache.plugins
  if type(plugins) ~= "table" then
    return nil
  end

  local names = {}
  for name, data in pairs(plugins) do
    if type(name) == "string" and type(data) == "table" and data.status == "update" then
      names[#names + 1] = name
    end
  end

  if #names == 0 then
    return nil
  end

  table.sort(names)
  limit = math.max(1, tonumber(limit) or 5)
  local shown = {}
  for i = 1, math.min(#names, limit) do
    shown[#shown + 1] = names[i]
  end

  local suffix = #names > limit and string.format(", +%d more", #names - limit) or ""
  return table.concat(shown, ", ") .. suffix
end

local function notify_check_start(online)
  local msg = online and "Checking plugin updates online..." or "Computing local plugin status (offline; no fetch)..."
  vim.notify(msg, vim.log.levels.INFO)
end

local function notify_check_result(online, counts)
  local label = online and "Online plugin check" or "Offline plugin status"
  local msg = label .. ": " .. format_check_counts(counts)
  local names = online and pending_update_names(5) or nil
  if names then
    msg = msg .. " (" .. names .. ")"
  elseif not online then
    msg = msg .. " (no remotes fetched)"
  end
  vim.notify(msg, vim.log.levels.INFO)
end

local semver_major = semver.semver_major
local semver_delta = semver.semver_delta

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

local function fetch_pack_remotes_async(names, callback, progress_callback)
  local function report_progress(done_count, total_count)
    if type(progress_callback) ~= "function" then
      return
    end
    vim.schedule(function()
      progress_callback({
        done = done_count,
        total = total_count,
      })
    end)
  end

  local ok, plugins = pcall(vim.pack.get, names, { info = false })
  if not ok or type(plugins) ~= "table" then
    notify_err("Failed to read vim.pack plugins")
    vim.schedule(function()
      callback({})
    end)
    return
  end

  local targets = {}
  for _, plugin in ipairs(plugins) do
    local name = plugin and plugin.spec and plugin.spec.name
    local path = plugin and plugin.path
    if type(name) == "string" and name ~= "" and type(path) == "string" and path ~= "" then
      targets[#targets + 1] = { name = name, path = path }
    end
  end

  if #targets == 0 then
    vim.schedule(function()
      callback({})
    end)
    return
  end

  local env = vim.fn.environ()
  env.GIT_DIR = nil
  env.GIT_WORK_TREE = nil
  local max_jobs = tonumber(vim.g.pack_dashboard_fetch_concurrency) or 8
  max_jobs = math.max(1, math.min(#targets, max_jobs))

  local errors = {}
  local next_index = 1
  local running = 0
  local done = 0
  local finished = false
  report_progress(0, #targets)

  local function finish_if_done()
    if finished or done < #targets then
      return
    end
    finished = true
    vim.schedule(function()
      callback(errors)
    end)
  end

  local function launch_next()
    while running < max_jobs and next_index <= #targets do
      local target = targets[next_index]
      next_index = next_index + 1
      running = running + 1
      vim.system({
        "git",
        "-c",
        "gc.auto=0",
        "fetch",
        "--quiet",
        "--tags",
        "--force",
        "--recurse-submodules=yes",
        "origin",
      }, {
        cwd = target.path,
        text = true,
        env = env,
        clear_env = true,
      }, function(out)
        running = running - 1
        done = done + 1
        report_progress(done, #targets)
        if out.code ~= 0 then
          errors[target.name] = vim.trim(out.stderr or out.stdout or "git fetch failed")
        end
        vim.schedule(launch_next)
        finish_if_done()
      end)
    end
    finish_if_done()
  end

  launch_next()
end

local function scan_updates_to_cache(online, names, merge, opts)
  opts = opts or {}
  local update_opts = nil
  if opts.update_offline or not online then
    update_opts = { offline = true }
  end
  vim.pack.update(names, update_opts)
  local counts, report_bufnr = refresh_pack_report_cache_from_report_buffer(merge)
  if not counts then
    notify_err("Failed to capture vim.pack report buffer")
    return false
  end
  if opts.record_counts ~= false then
    pack_report_cache.last_check_counts = counts
  end
  if type(opts.fetch_errors) == "table" then
    for name, err in pairs(opts.fetch_errors) do
      if type(name) == "string" and name ~= "" then
        pack_report_cache.plugins[name] = {
          status = "error",
          pending_updates = tostring(err or "git fetch failed"),
        }
        if opts.record_counts ~= false then
          counts.error = (tonumber(counts.error) or 0) + 1
        end
      end
    end
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
  return true, counts
end

-- Drop cache and persisted-UI entries that no longer correspond to a managed
-- plugin. Prevents `selected_names` from growing monotonically and prevents
-- dead rows from polluting `pack_report_cache`. Returns true when anything was
-- purged so the caller can persist updated state.
local function purge_stale_dashboard_state()
  local ok, current = pcall(vim.pack.get, nil, { info = false })
  if not ok or type(current) ~= "table" then
    return false
  end

  local valid_names = {}
  for _, plugin in ipairs(current) do
    local name = plugin and plugin.spec and plugin.spec.name
    if type(name) == "string" and name ~= "" then
      valid_names[name] = true
    end
  end
  if next(valid_names) == nil then
    return false
  end

  local dirty = false
  if type(pack_report_cache.plugins) == "table" then
    for name in pairs(pack_report_cache.plugins) do
      if not valid_names[name] then
        pack_report_cache.plugins[name] = nil
        dirty = true
      end
    end
  end

  if type(dashboard_ui_cache.selected_names) == "table" then
    local kept = {}
    local changed = false
    for _, name in ipairs(dashboard_ui_cache.selected_names) do
      if valid_names[name] then
        kept[#kept + 1] = name
      else
        changed = true
      end
    end
    if changed then
      dashboard_ui_cache.selected_names = kept
      dirty = true
    end
  end

  return dirty
end

local function ensure_dashboard_cache(online, force_scan)
  if purge_stale_dashboard_state() then
    write_persisted_state()
  end

  if force_scan and not online then
    return scan_updates_to_cache(false, nil, false, { mark_online = false, mark_offline = true })
  end
  if type(pack_report_cache.plugins) == "table" and next(pack_report_cache.plugins) ~= nil then
    return true
  end

  return true
end

local function collect_dashboard_rows()
  local ok, plugins = pcall(vim.pack.get, nil, { info = false })
  if not ok then
    notify_err("Failed to read vim.pack plugins")
    return {}
  end

  -- Only flag orphans once `core.plugins.setup` has advertised its declared
  -- set. Before that the cache is empty and we must not mark everything as
  -- orphaned (e.g. when a user runs `:PackDashboard` from a minimal config).
  local orphan_flagging = next(declared_names_cache) ~= nil

  local rows = {}
  for _, plugin in ipairs(plugins) do
    local name = plugin.spec.name
    local p_data = pack_report_cache.plugins[name] or {}
    local status = p_data.status or "unknown"
    local source = p_data.source or plugin.spec.src
    local diff_url = p_data.diff_url or source_to_compare_url(source, p_data.rev_before, p_data.rev_after)
    local breaking = p_data.breaking
    local is_orphan = orphan_flagging and not declared_names_cache[name]
    if is_orphan then
      -- Orphans supersede any prior update/same/error status coming from the
      -- `vim.pack.update` report: the user should be nudged to clean them
      -- before seeing them as an upgradeable row.
      status = "orphan"
      breaking = nil
    end
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
      is_orphan = is_orphan or nil,
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
  -- Singleton guard: reuse the existing dashboard window when already open.
  -- With `force_scan` (i.e. `:PackDashboard!`) close the current one so the
  -- fresh scan rebuilds it from scratch.
  if dashboard_winid and vim.api.nvim_win_is_valid(dashboard_winid) then
    if force_scan then
      pcall(vim.api.nvim_win_close, dashboard_winid, true)
      dashboard_winid = nil
    else
      pcall(vim.api.nvim_set_current_win, dashboard_winid)
      return
    end
  end

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
        orphan = "\u{f1f8}",
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
      orphan = "O",
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
    orphan = icons.orphan,
  }
  -- Orphans sit between updates and errors: they demand attention (they're
  -- disk drift + unmanaged code) but they're not build/fetch failures.
  local status_rank = { update = 1, orphan = 2, error = 3, same = 4, unknown = 5 }
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

    dashboard_winid = winid
    vim.api.nvim_create_autocmd("WinClosed", {
      once = true,
      pattern = tostring(winid),
      callback = function()
        if dashboard_winid == winid then
          dashboard_winid = nil
        end
      end,
    })
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
        include = row.status == "update" or row.status == "error" or row.status == "orphan"
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
    local counts = { update = 0, same = 0, error = 0, unknown = 0, orphan = 0, breaking = 0 }
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
    if not vim.api.nvim_buf_is_valid(bufnr) then
      return
    end
    ensure_dashboard_highlights()
    local mode = pack_report_cache.mode or "unknown"
    local counts = summary_counts()
    local visible = visible_rows()
    local sel_visible = selected_count(true)
    local sel_total = selected_count(false)
    local checked_stamp = format_cache_stamp(pack_report_cache.updated_at)
    local online_stamp = format_cache_stamp(pack_report_cache.last_online_at)
    local offline_stamp = format_cache_stamp(pack_report_cache.last_offline_at)
    local applied_stamp = format_cache_stamp(pack_report_cache.last_applied_at)
    local applied_count = tonumber(pack_report_cache.last_applied_count) or 0
    local raw = pack_report_cache.last_check_counts
    local raw_line = "last-result raw: n/a (run r for online check)"
    if type(raw) == "table" then
      raw_line = string.format(
        "last-result raw: update:%d same:%d error:%d",
        tonumber(raw.update) or 0,
        tonumber(raw.same) or 0,
        tonumber(raw.error) or 0
      )
    end
    raw_line = string.format("%s   online:%s   offline:%s", raw_line, online_stamp, offline_stamp)
    if dashboard_online_check_running then
      local progress = dashboard_online_check_progress
      if type(progress) == "table" and progress.phase == "status" then
        raw_line = raw_line .. "   check:status"
      elseif type(progress) == "table" and tonumber(progress.total) and progress.total > 0 then
        raw_line = raw_line .. string.format("   check:fetch:%d/%d", tonumber(progress.done) or 0, progress.total)
      else
        raw_line = raw_line .. "   check:fetch:start"
      end
    end
    local win_width = (winid and vim.api.nvim_win_is_valid(winid)) and vim.api.nvim_win_get_width(winid)
      or vim.o.columns
    local row_width = math.max(80, win_width - 2)
    local sep_char = use_nerd_font and "─" or "-"
    local sep = string.rep(sep_char, row_width)

    local title = use_nerd_font and "󰒲  vim.pack dashboard" or "vim.pack dashboard"
    local title_line = string.format(
      "%s   mode:%s   result:%s   applied:%s (%d)   selected:%d/%d",
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
        "%s %d   %s %d   %s %d   %s %d   %s %d   %s %d",
        icons.update,
        counts.update,
        icons.same,
        counts.same,
        icons.error,
        counts.error,
        icons.unknown,
        counts.unknown,
        icons.orphan,
        counts.orphan,
        icons.risk_break,
        counts.breaking
      )
    else
      stats_line = string.format(
        "updates:%d  same:%d  errors:%d  unknown:%d  orphan:%d  breaking:%d",
        counts.update,
        counts.same,
        counts.error,
        counts.unknown,
        counts.orphan,
        counts.breaking
      )
    end
    local controls_line = string.format(
      "r online-refresh  R offline-status  <CR>/u/U update-pending  C clean-orphans  f filter:%s  s sort:%s  / search:%s  a sel-all  o link  K details  ? help",
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
      orphan = "PackDashboardStatusOrphan",
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

    -- Row layout: `pad_cell(sel, 3) .. " " .. pad_cell(icon, 2) .. " " ..
    --              pad_cell(risk, 2) .. " " .. ...`.
    -- Extmarks take BYTE offsets, not display columns. SEL/RK chars are
    -- always ASCII (1 byte each), but the ST status icon is a 3-byte
    -- nerd-font glyph in icon mode and a 1-byte ASCII char in ASCII mode,
    -- so the RK offsets have to shift accordingly. The earlier hardcoded
    -- `rk_start=7` landed on ST-pad + separator spaces and leaked the
    -- `DiffAdd`/`DiagnosticWarn` background onto those cells, producing
    -- spurious colored squares next to the status arrow.
    local sel_start = 0
    local sel_end = sel_start + 3 -- "[ ]" or "[x]" → 3 bytes
    local st_icon_bytes = use_nerd_font and 3 or 1
    local st_start = sel_end + 1 -- +1 separator space
    local st_end = st_start + st_icon_bytes + 1 -- +1 for pad space
    local rk_start = st_end + 1 -- +1 separator space
    local rk_end = rk_start + 2 -- risk char (1) + pad space (1)

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

  local function count_fetch_errors(fetch_errors)
    local count = 0
    for _ in pairs(fetch_errors or {}) do
      count = count + 1
    end
    return count
  end

  local function update_dashboard_after_scan(next_online, counts, current_name, should_notify)
    rows = collect_dashboard_rows()
    local previous_selected = selected
    selected = {}
    for _, row in ipairs(rows) do
      if previous_selected[row.name] then
        selected[row.name] = true
      end
    end
    render()
    persist_dashboard_ui_state()
    if current_name and winid and vim.api.nvim_win_is_valid(winid) then
      for line, row in pairs(row_by_line) do
        if row.name == current_name then
          pcall(vim.api.nvim_win_set_cursor, winid, { line, 0 })
          break
        end
      end
    end
    if should_notify then
      notify_check_result(next_online, counts)
    end
  end

  local function refresh(next_online, names, merge, opts)
    opts = opts or {}
    local should_notify = opts.notify ~= false
    local current = row_at_cursor()
    local current_name = current and current.name or nil
    if next_online and opts.async then
      if dashboard_online_check_running then
        render()
        if should_notify then
          vim.notify("Online plugin check already running", vim.log.levels.INFO)
        end
        return
      end
      dashboard_online_check_running = true
      dashboard_online_check_progress = nil
      if should_notify then
        notify_check_start(next_online)
      end
      render()
      fetch_pack_remotes_async(names, function(fetch_errors)
        dashboard_online_check_progress = {
          phase = "status",
          done = dashboard_online_check_progress and dashboard_online_check_progress.total or 0,
          total = dashboard_online_check_progress and dashboard_online_check_progress.total or 0,
        }
        render()
        local scan_opts = vim.tbl_extend("force", opts, { update_offline = true, fetch_errors = fetch_errors })
        scan_opts.async = nil
        local ok, counts = scan_updates_to_cache(next_online, names, merge, scan_opts)
        dashboard_online_check_running = false
        dashboard_online_check_progress = nil
        if ok then
          update_dashboard_after_scan(next_online, counts, current_name, should_notify)
          local failed = count_fetch_errors(fetch_errors)
          if failed > 0 then
            vim.notify(string.format("Plugin fetch failed for %d repo(s); see error rows", failed), vim.log.levels.WARN)
          end
        else
          render()
        end
      end, function(progress)
        dashboard_online_check_progress = progress
        render()
      end)
      return
    end

    if should_notify then
      notify_check_start(next_online)
    end

    local ok, counts = scan_updates_to_cache(next_online, names, merge, opts)
    if ok then
      update_dashboard_after_scan(next_online, counts, current_name, should_notify)
    end
  end

  local function apply_updates(filtered)
    vim.pack.update(filtered, { force = true })
    pack_report_cache.last_applied_at = os.time()
    pack_report_cache.last_applied_count = #filtered
    write_persisted_state()
    pcall(refresh_version_policy_if_needed)
    refresh(false, filtered, true, { mark_online = false, mark_offline = false, record_counts = false, notify = false })
  end

  local function update_by_names(names, empty_msg, noop_msg)
    if #names == 0 then
      vim.notify(empty_msg or "No plugins selected", vim.log.levels.WARN)
      return
    end

    local status_by_name = {}
    for _, row in ipairs(rows) do
      status_by_name[row.name] = row.status
    end

    local filtered = {}
    local seen = {}
    for _, name in ipairs(names) do
      if type(name) == "string" and name ~= "" and not seen[name] and status_by_name[name] == "update" then
        seen[name] = true
        filtered[#filtered + 1] = name
      end
    end

    if #filtered == 0 then
      vim.notify(noop_msg or "Selected plugins are already up to date", vim.log.levels.INFO)
      return
    end

    -- When any plugin carries a `risk_break` signal (major-version bump or
    -- commit metadata flagged by `infer_breaking_status`), gate the force
    -- update behind a confirmation. `vim.g.pack_dashboard_skip_risk_confirm`
    -- opts out for users who prefer the old always-force behavior.
    if vim.g.pack_dashboard_skip_risk_confirm ~= true then
      local risky = {}
      local selected_set = {}
      for _, name in ipairs(filtered) do
        selected_set[name] = true
      end
      for _, row in ipairs(rows) do
        if selected_set[row.name] and row.breaking == true then
          risky[#risky + 1] = row.name
        end
      end
      if #risky > 0 then
        local msg = string.format(
          "%d plugin(s) flagged as risky (%s).\nProceed with force update? [y/N] ",
          #risky,
          table.concat(risky, ", ")
        )
        local answer = vim.fn.confirm(msg, "&Yes\n&No", 2)
        if answer ~= 1 then
          vim.notify("Update cancelled", vim.log.levels.INFO)
          return
        end
      end
    end

    apply_updates(filtered)
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
    refresh(true, nil, nil, { mark_online = true, mark_offline = false, async = true })
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
    update_by_names({ row.name }, "No plugin on current row", "Plugin has no pending update")
  end, { buffer = bufnr, nowait = true, silent = true })

  vim.keymap.set("n", "u", function()
    local names = selected_names(true)
    if #names == 0 then
      local current = row_at_cursor()
      if current then
        names = { current.name }
      end
    end
    update_by_names(names, "No selected plugins", "No selected/cursor plugins have pending updates")
  end, { buffer = bufnr, nowait = true, silent = true })

  vim.keymap.set("n", "U", function()
    local names = {}
    for _, row in ipairs(visible_rows()) do
      names[#names + 1] = row.name
    end
    update_by_names(names, "No visible plugins to update", "No visible plugins have pending updates")
  end, { buffer = bufnr, nowait = true, silent = true })

  local function clean_orphan_rows(targets, scope_label)
    if #targets == 0 then
      vim.notify("No orphan plugins to clean", vim.log.levels.INFO)
      return
    end

    if vim.g.pack_dashboard_skip_clean_confirm ~= true then
      local preview = table.concat(targets, ", ")
      if #preview > 240 then
        preview = preview:sub(1, 237) .. "..."
      end
      local msg = string.format("Clean %d %s orphan plugin(s)?\n  %s\nContinue? [y/N] ", #targets, scope_label, preview)
      local answer = vim.fn.confirm(msg, "&Yes\n&No", 2)
      if answer ~= 1 then
        vim.notify("Clean cancelled", vim.log.levels.INFO)
        return
      end
    end

    local ok_del, err = pcall(vim.pack.del, targets)
    if not ok_del then
      vim.notify("vim.pack.del failed: " .. tostring(err), vim.log.levels.ERROR)
      return
    end

    for _, name in ipairs(targets) do
      if type(pack_report_cache.plugins) == "table" then
        pack_report_cache.plugins[name] = nil
      end
      selected[name] = nil
    end
    write_persisted_state()

    rows = collect_dashboard_rows()
    render()
    persist_dashboard_ui_state()
    vim.notify(string.format("Cleaned %d orphan plugin(s)", #targets), vim.log.levels.INFO)
  end

  vim.keymap.set("n", "C", function()
    local orphans = {}
    local selected_orphans = {}
    for _, row in ipairs(rows) do
      if row.is_orphan then
        orphans[#orphans + 1] = row.name
        if selected[row.name] then
          selected_orphans[#selected_orphans + 1] = row.name
        end
      end
    end
    -- Default target: selected orphans if any exist, otherwise all orphans.
    -- Mirrors lazy.nvim's `C` UX of "clean what's visible" while respecting
    -- explicit selection when the user has picked a subset.
    if #selected_orphans > 0 then
      clean_orphan_rows(selected_orphans, "selected")
    else
      clean_orphan_rows(orphans, "all")
    end
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
      "r          refresh online (fetches remotes)",
      "R          offline status (no fetch; may not show remote updates)",
      "f          cycle filter (all -> updates -> issues -> selected)",
      "s          cycle sort (status <-> name)",
      "/ / c      set search / clear search",
      "<Space>/x  toggle row selection (also works in visual mode)",
      "a / A      select all visible / clear all selection",
      "<CR>       update plugin at cursor",
      "u / U      update pending selected (or cursor if none) / all pending listed",
      "C          clean orphan plugins (selected orphans, else all orphans)",
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

-- Path to the lockfile that `vim.pack` already maintains. Discovered from the
-- 0.12 runtime: `stdpath('config') .. '/nvim-pack-lock.json'`. Exposed so the
-- export/import commands agree with the upstream location.
function M.lockfile_path()
  return vim.fs.joinpath(vim.fn.stdpath("config"), "nvim-pack-lock.json")
end

-- Copy the live lockfile to `destination`. Parent directory is created if
-- missing. Returns `ok, err_or_path`.
function M.export_lockfile(destination)
  if type(destination) ~= "string" or destination == "" then
    return false, "destination path is required"
  end

  local expanded = vim.fn.expand(destination)
  if vim.fn.isdirectory(expanded) == 1 then
    expanded = vim.fs.joinpath(expanded, "nvim-pack-lock.json")
  end

  local src = M.lockfile_path()
  if vim.fn.filereadable(src) ~= 1 then
    return false, "lockfile does not exist yet: " .. src
  end

  local parent = vim.fs.dirname(expanded)
  if parent and parent ~= "" and vim.fn.isdirectory(parent) ~= 1 then
    pcall(vim.fn.mkdir, parent, "p")
  end

  local ok_read, lines = pcall(vim.fn.readfile, src, "b")
  if not ok_read or type(lines) ~= "table" then
    return false, "failed to read lockfile"
  end
  local ok_write, err = pcall(vim.fn.writefile, lines, expanded, "b")
  if not ok_write then
    return false, tostring(err or "failed to write lockfile")
  end

  return true, expanded
end

-- Copy a lockfile from `source` on top of the live lockfile. Validates JSON
-- schema before overwriting. Returns `ok, err_or_path`.
function M.import_lockfile(source)
  if type(source) ~= "string" or source == "" then
    return false, "source path is required"
  end

  local expanded = vim.fn.expand(source)
  if vim.fn.isdirectory(expanded) == 1 then
    expanded = vim.fs.joinpath(expanded, "nvim-pack-lock.json")
  end
  if vim.fn.filereadable(expanded) ~= 1 then
    return false, "source lockfile not readable: " .. expanded
  end

  local ok_read, lines = pcall(vim.fn.readfile, expanded, "b")
  if not ok_read or type(lines) ~= "table" or #lines == 0 then
    return false, "failed to read source lockfile"
  end

  local ok_decode, decoded = pcall(vim.json.decode, table.concat(lines, "\n"))
  if not ok_decode or type(decoded) ~= "table" or type(decoded.plugins) ~= "table" then
    return false, "source file does not match the vim.pack lockfile schema"
  end

  local dest = M.lockfile_path()
  local parent = vim.fs.dirname(dest)
  if parent and parent ~= "" and vim.fn.isdirectory(parent) ~= 1 then
    pcall(vim.fn.mkdir, parent, "p")
  end
  local ok_write, err = pcall(vim.fn.writefile, lines, dest, "b")
  if not ok_write then
    return false, tostring(err or "failed to write lockfile")
  end

  return true, dest
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
    local checked = format_cache_stamp(pack_report_cache.updated_at)
    local online = format_cache_stamp(pack_report_cache.last_online_at)
    local offline = format_cache_stamp(pack_report_cache.last_offline_at)
    local applied = format_cache_stamp(pack_report_cache.last_applied_at)
    local applied_count = tonumber(pack_report_cache.last_applied_count) or 0
    vim.notify(
      string.format(
        "PackDashboard last-check [%s] mode:%s result:%s online:%s offline:%s applied:%s (%d)",
        raw_text,
        pack_report_cache.mode or "unknown",
        checked,
        online,
        offline,
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

  vim.api.nvim_create_user_command("PackLockInfo", function()
    local path = M.lockfile_path()
    if vim.fn.filereadable(path) ~= 1 then
      vim.notify("vim.pack lockfile not found at " .. path, vim.log.levels.WARN)
      return
    end
    local ok_read, lines = pcall(vim.fn.readfile, path)
    local plugins = 0
    if ok_read and type(lines) == "table" then
      local ok_decode, decoded = pcall(vim.json.decode, table.concat(lines, "\n"))
      if ok_decode and type(decoded) == "table" and type(decoded.plugins) == "table" then
        for _ in pairs(decoded.plugins) do
          plugins = plugins + 1
        end
      end
    end
    local stat = vim.uv.fs_stat(path)
    local mtime = stat and os.date("%Y-%m-%d %H:%M:%S", stat.mtime.sec) or "unknown"
    vim.notify(
      string.format("vim.pack lockfile: %s\n  plugins: %d\n  mtime:   %s", path, plugins, mtime),
      vim.log.levels.INFO
    )
  end, {
    desc = "Show vim.pack lockfile path, plugin count, mtime",
  })

  vim.api.nvim_create_user_command("PackLockExport", function(cmd)
    local dest = cmd.args
    if type(dest) ~= "string" or dest == "" then
      vim.notify("Usage: :PackLockExport <path>", vim.log.levels.WARN)
      return
    end
    local ok, result = M.export_lockfile(dest)
    if ok then
      vim.notify("Exported lockfile → " .. result, vim.log.levels.INFO)
    else
      vim.notify("PackLockExport failed: " .. tostring(result), vim.log.levels.ERROR)
    end
  end, {
    nargs = 1,
    complete = "file",
    desc = "Copy nvim-pack-lock.json to an arbitrary path (for dotfile sync)",
  })

  vim.api.nvim_create_user_command("PackPolicyRebuild", function(cmd)
    local arg = vim.trim(cmd.args or "")
    local target = arg ~= "" and arg or nil
    local ok = rebuild_version_policy(target)
    if ok then
      local version_policy = load_version_policy() or { plugins = {} }
      if target then
        local info = version_policy.plugins and version_policy.plugins[target]
        if info then
          vim.notify(
            string.format(
              "Rebuilt policy for %s: strategy=%s\n  %s",
              target,
              tostring(info.strategy),
              tostring(info.reason or "")
            ),
            vim.log.levels.INFO
          )
        else
          vim.notify("Rebuilt policy, but no entry recorded for " .. target, vim.log.levels.WARN)
        end
      else
        local count = 0
        local tags, branch = 0, 0
        for _, info in pairs(version_policy.plugins or {}) do
          count = count + 1
          if info.strategy == "tags" then
            tags = tags + 1
          elseif info.strategy == "branch" then
            branch = branch + 1
          end
        end
        vim.notify(
          string.format("Rebuilt version policy: %d plugins (%d tags, %d branch)", count, tags, branch),
          vim.log.levels.INFO
        )
      end
    else
      vim.notify("PackPolicyRebuild failed", vim.log.levels.ERROR)
    end
  end, {
    nargs = "?",
    complete = function(arglead)
      local ok, plug_data = pcall(vim.pack.get, nil, { info = false })
      if not ok or type(plug_data) ~= "table" then
        return {}
      end
      local out = {}
      for _, p in ipairs(plug_data) do
        local n = p and p.spec and p.spec.name
        if type(n) == "string" and (arglead == "" or n:find(arglead, 1, true)) then
          out[#out + 1] = n
        end
      end
      table.sort(out)
      return out
    end,
    desc = "Clear and recompute the cached per-plugin tag/branch heuristic. Pass plugin name for a targeted rebuild.",
  })

  vim.api.nvim_create_user_command("PackLockImport", function(cmd)
    local source = cmd.args
    if type(source) ~= "string" or source == "" then
      vim.notify("Usage: :PackLockImport <path>", vim.log.levels.WARN)
      return
    end
    local ok, result = M.import_lockfile(source)
    if ok then
      vim.notify(
        "Imported lockfile from " .. source .. " → " .. result .. ". Restart or run :PackSync to apply.",
        vim.log.levels.INFO
      )
    else
      vim.notify("PackLockImport failed: " .. tostring(result), vim.log.levels.ERROR)
    end
  end, {
    nargs = 1,
    complete = "file",
    desc = "Overwrite nvim-pack-lock.json from a path (for dotfile sync)",
  })
end

return M
