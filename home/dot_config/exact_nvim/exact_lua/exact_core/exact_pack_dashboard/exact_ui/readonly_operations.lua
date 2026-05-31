local analysis = require("core.pack_dashboard.analysis")
local report = require("core.pack_dashboard.report")
local state = require("core.pack_dashboard.state")
local policy = require("core.pack.policy")
local view = require("core.pack_dashboard.ui.view")
local refresh = require("core.pack_dashboard.ui.refresh")

local M = {}

local refresh_version_policy_if_needed = policy.refresh_version_policy_if_needed

function M.update_by_names(ctx, names, empty_msg, noop_msg)
  if #names == 0 then
    vim.notify(empty_msg or "No plugins selected", vim.log.levels.WARN)
    return
  end

  local status_by_name = {}
  for _, row in ipairs(ctx.rows) do
    status_by_name[row.name] = row.status
  end

  local filtered, seen = {}, {}
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

  if vim.g.pack_dashboard_skip_risk_confirm ~= true then
    local risky, selected_set = {}, {}
    for _, name in ipairs(filtered) do
      selected_set[name] = true
    end
    for _, row in ipairs(ctx.rows) do
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
      if vim.fn.confirm(msg, "&Yes\n&No", 2) ~= 1 then
        vim.notify("Update cancelled", vim.log.levels.INFO)
        return
      end
    end
  end

  vim.pack.update(filtered, { force = true })
  state.pack_report_cache.last_applied_at = os.time()
  state.pack_report_cache.last_applied_count = #filtered
  state.write_persisted_state()
  pcall(refresh_version_policy_if_needed)
  refresh.refresh(
    ctx,
    false,
    filtered,
    true,
    { mark_online = false, mark_offline = false, record_counts = false, notify = false }
  )
end

function M.clean_orphan_rows(ctx, targets, scope_label)
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
    if vim.fn.confirm(msg, "&Yes\n&No", 2) ~= 1 then
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
    if type(state.pack_report_cache.plugins) == "table" then
      state.pack_report_cache.plugins[name] = nil
    end
    ctx.selected[name] = nil
  end
  state.write_persisted_state()
  ctx.rows = report.collect_dashboard_rows()
  view.render(ctx)
  refresh.persist_ui_state(ctx)
  vim.notify(string.format("Cleaned %d orphan plugin(s)", #targets), vim.log.levels.INFO)
end

function M.heal_drift_rows(ctx, targets)
  if #targets == 0 then
    vim.notify("No drifted plugins to heal", vim.log.levels.INFO)
    return
  end

  local ok_update, err = pcall(vim.pack.update, targets, { offline = true })
  if not ok_update then
    vim.notify("vim.pack.update failed: " .. tostring(err), vim.log.levels.ERROR)
    return
  end

  state.version_flags_cache = {}
  state.version_flags_scanned = false
  ctx.rows = report.collect_dashboard_rows()
  view.render(ctx)
  analysis.refresh_version_flags_async(function()
    ctx.rows = report.collect_dashboard_rows()
    view.render(ctx)
  end)
  refresh.persist_ui_state(ctx)
  vim.notify(string.format("Re-checked out %d drifted plugin(s)", #targets), vim.log.levels.INFO)
end

function M.open_diff_or_repo_for_row(row)
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

return M
