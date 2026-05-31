local state = require("core.pack_dashboard.state")
local analysis = require("core.pack_dashboard.analysis")
local notify = require("core.pack_dashboard.report.notify")
local parser = require("core.pack_dashboard.report.parser")

local M = {}

local function scan_updates_to_cache(online, names, merge, opts)
  opts = opts or {}
  local update_opts = nil
  if opts.update_offline or not online then
    update_opts = { offline = true }
  end
  vim.pack.update(names, update_opts)
  local counts, report_bufnr = parser.refresh_pack_report_cache_from_report_buffer(merge)
  if not counts then
    notify.notify_err("Failed to capture vim.pack report buffer")
    return false
  end
  if opts.record_counts ~= false then
    state.pack_report_cache.last_check_counts = counts
  end
  if type(opts.fetch_errors) == "table" then
    for name, err in pairs(opts.fetch_errors) do
      if type(name) == "string" and name ~= "" then
        state.pack_report_cache.plugins[name] = {
          status = "error",
          pending_updates = tostring(err or "git fetch failed"),
        }
        if opts.record_counts ~= false then
          counts.error = (tonumber(counts.error) or 0) + 1
        end
      end
    end
  end
  state.pack_report_cache.mode = online and "online" or "offline"
  if online and opts.mark_online then
    state.pack_report_cache.last_online_at = os.time()
  elseif (not online) and opts.mark_offline then
    state.pack_report_cache.last_offline_at = os.time()
  end
  state.write_persisted_state()
  if report_bufnr and vim.api.nvim_buf_is_valid(report_bufnr) then
    pcall(vim.api.nvim_buf_delete, report_bufnr, { force = true })
  end
  return true, counts
end

-- Drop cache and persisted-UI entries that no longer correspond to a managed
-- plugin. Prevents `selected_names` from growing monotonically and prevents
-- dead rows from polluting `state.pack_report_cache`. Returns true when anything was
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
  if type(state.pack_report_cache.plugins) == "table" then
    for name in pairs(state.pack_report_cache.plugins) do
      if not valid_names[name] then
        state.pack_report_cache.plugins[name] = nil
        dirty = true
      end
    end
  end

  if type(state.dashboard_ui_cache.selected_names) == "table" then
    local kept = {}
    local changed = false
    for _, name in ipairs(state.dashboard_ui_cache.selected_names) do
      if valid_names[name] then
        kept[#kept + 1] = name
      else
        changed = true
      end
    end
    if changed then
      state.dashboard_ui_cache.selected_names = kept
      dirty = true
    end
  end

  return dirty
end

local function ensure_dashboard_cache(online, force_scan)
  if purge_stale_dashboard_state() then
    state.write_persisted_state()
  end

  if force_scan and not online then
    return scan_updates_to_cache(false, nil, false, { mark_online = false, mark_offline = true })
  end
  if type(state.pack_report_cache.plugins) == "table" and next(state.pack_report_cache.plugins) ~= nil then
    return true
  end

  return true
end

local function collect_dashboard_rows()
  -- Keep the hot path fast: `info = true` shells out to git for every plugin
  -- (~700ms for this config). Drift/risky checks gather tags only for the small
  -- subset of rows whose declared version can actually use them, asynchronously.
  local ok, plugins = pcall(vim.pack.get, nil, { info = false })
  if not ok then
    notify.notify_err("Failed to read vim.pack plugins")
    return {}
  end

  -- Only flag orphans once `core.plugins.setup` has advertised its declared
  -- set. Before that the cache is empty and we must not mark everything as
  -- orphaned (e.g. when a user runs `:PackDashboard` from a minimal config).
  local orphan_flagging = next(state.declared_names_cache) ~= nil
  local version_flagging = next(state.declared_versions_cache) ~= nil

  local rows = {}
  for _, plugin in ipairs(plugins) do
    local name = plugin.spec.name
    local p_data = state.pack_report_cache.plugins[name] or {}
    local status = p_data.status or "unknown"
    local source = p_data.source or plugin.spec.src
    local diff_url = p_data.diff_url or analysis.source_to_compare_url(source, p_data.rev_before, p_data.rev_after)
    local breaking = p_data.breaking
    local is_orphan = orphan_flagging and not state.declared_names_cache[name]

    -- Spec-vs-disk version drift and risky `version = "*"` pins. Only meaningful
    -- for declared (non-orphan) plugins once versions have been published.
    local is_drift = false
    local is_risky_pin = false
    if version_flagging and not is_orphan then
      local flags = state.version_flags_cache[name]
      is_drift = type(flags) == "table" and flags.drift == true
      is_risky_pin = type(flags) == "table" and flags.risky == true
    end

    if is_orphan then
      -- Orphans supersede any prior update/same/error status coming from the
      -- `vim.pack.update` report: the user should be nudged to clean them
      -- before seeing them as an upgradeable row.
      status = "orphan"
      breaking = nil
    elseif is_drift then
      -- Drift (checkout no longer satisfies the spec) outranks update/same:
      -- the user changed intent and the on-disk ref must be re-resolved.
      status = "drift"
      breaking = nil
    elseif is_risky_pin then
      status = "risky"
      breaking = nil
    end
    if breaking == nil and status == "update" then
      p_data.source = source
      p_data.diff_url = diff_url
      p_data.breaking = analysis.infer_breaking_status(p_data)
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
      repo_url = analysis.source_to_repo_url(source),
      is_orphan = is_orphan or nil,
      is_drift = is_drift or nil,
      is_risky_pin = is_risky_pin or nil,
    }
  end

  for _, row in ipairs(rows) do
    if not row.diff_url and row.status == "update" and row.repo_url then
      local from_ref = row.current_version or row.rev_before
      local to_ref = row.target_version or row.rev_after
      row.diff_url = analysis.repo_to_compare_url(row.repo_url, from_ref, to_ref)
    end
  end

  return rows
end

M.scan_updates_to_cache = scan_updates_to_cache
M.ensure_dashboard_cache = ensure_dashboard_cache
M.collect_dashboard_rows = collect_dashboard_rows

return M
