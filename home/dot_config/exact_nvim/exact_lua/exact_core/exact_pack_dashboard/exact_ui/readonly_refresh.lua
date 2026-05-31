local report = require("core.pack_dashboard.report")
local state = require("core.pack_dashboard.state")
local view = require("core.pack_dashboard.ui.view")
local rows = require("core.pack_dashboard.ui.rows")

local M = {}

local function count_fetch_errors(fetch_errors)
  local count = 0
  for _ in pairs(fetch_errors or {}) do
    count = count + 1
  end
  return count
end

function M.update_after_scan(ctx, next_online, counts, current_name, should_notify)
  ctx.rows = report.collect_dashboard_rows()
  local previous_selected = ctx.selected
  ctx.selected = {}
  for _, row in ipairs(ctx.rows) do
    if previous_selected[row.name] then
      ctx.selected[row.name] = true
    end
  end
  view.render(ctx)
  M.persist_ui_state(ctx)
  if current_name and ctx.winid and vim.api.nvim_win_is_valid(ctx.winid) then
    for line, row in pairs(ctx.row_by_line) do
      if row.name == current_name then
        pcall(vim.api.nvim_win_set_cursor, ctx.winid, { line, 0 })
        break
      end
    end
  end
  if should_notify then
    report.notify_check_result(next_online, counts)
  end
end

function M.refresh(ctx, next_online, names, merge, opts)
  opts = opts or {}
  local should_notify = opts.notify ~= false
  local current = rows.row_at_cursor(ctx)
  local current_name = current and current.name or nil
  if next_online and opts.async then
    if ctx.online_check_running then
      view.render(ctx)
      if should_notify then
        vim.notify("Online plugin check already running", vim.log.levels.INFO)
      end
      return
    end
    ctx.online_check_running = true
    ctx.online_check_progress = nil
    if should_notify then
      report.notify_check_start(next_online)
    end
    view.render(ctx)
    report.fetch_pack_remotes_async(names, function(fetch_errors)
      ctx.online_check_progress = {
        phase = "status",
        done = ctx.online_check_progress and ctx.online_check_progress.total or 0,
        total = ctx.online_check_progress and ctx.online_check_progress.total or 0,
      }
      view.render(ctx)
      local scan_opts = vim.tbl_extend("force", opts, { update_offline = true, fetch_errors = fetch_errors })
      scan_opts.async = nil
      local ok, counts = report.scan_updates_to_cache(next_online, names, merge, scan_opts)
      ctx.online_check_running = false
      ctx.online_check_progress = nil
      if ok then
        M.update_after_scan(ctx, next_online, counts, current_name, should_notify)
        local failed = count_fetch_errors(fetch_errors)
        if failed > 0 then
          vim.notify(string.format("Plugin fetch failed for %d repo(s); see error rows", failed), vim.log.levels.WARN)
        end
      else
        view.render(ctx)
      end
    end, function(progress)
      ctx.online_check_progress = progress
      view.render(ctx)
    end)
    return
  end

  if should_notify then
    report.notify_check_start(next_online)
  end
  local ok, counts = report.scan_updates_to_cache(next_online, names, merge, opts)
  if ok then
    M.update_after_scan(ctx, next_online, counts, current_name, should_notify)
  end
end

function M.persist_ui_state(ctx)
  local selected_names_out = {}
  for name, enabled in pairs(ctx.selected) do
    if enabled == true then
      selected_names_out[#selected_names_out + 1] = name
    end
  end
  table.sort(selected_names_out)
  state.dashboard_ui_cache.filter_mode =
    state.normalize_mode(ctx.filter_mode, { all = true, updates = true, issues = true, selected = true }, "all")
  state.dashboard_ui_cache.sort_mode = state.normalize_mode(ctx.sort_mode, { status = true, name = true }, "status")
  state.dashboard_ui_cache.search_text = (type(ctx.search_text) == "string" and ctx.search_text ~= "")
      and ctx.search_text
    or nil
  state.dashboard_ui_cache.selected_names = selected_names_out
  state.write_persisted_state()
end

return M
