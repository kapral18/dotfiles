local report = require("core.pack_dashboard.report")
local state = require("core.pack_dashboard.state")
local view = require("core.pack_dashboard.ui.view")
local rows = require("core.pack_dashboard.ui.rows")

local M = {}

local SPINNER_INTERVAL_MS = 90

-- Stop and dispose the per-row spinner animation timer, if running.
local function stop_spinner(ctx)
  if ctx.spinner_timer then
    pcall(function()
      ctx.spinner_timer:stop()
      ctx.spinner_timer:close()
    end)
    ctx.spinner_timer = nil
  end
end

-- Animate the inline spinner: advance the frame and rewrite only the rows that
-- are still in-flight (plus the header status line for live progress), so the
-- animation never triggers a full-table redraw.
local function start_spinner(ctx)
  stop_spinner(ctx)
  local timer = vim.uv.new_timer()
  if not timer then
    return
  end
  ctx.spinner_timer = timer
  timer:start(
    SPINNER_INTERVAL_MS,
    SPINNER_INTERVAL_MS,
    vim.schedule_wrap(function()
      -- Self-dispose if the dashboard buffer was closed mid-refresh so the
      -- libuv timer never leaks past the window's lifetime.
      if not (ctx.bufnr and vim.api.nvim_buf_is_valid(ctx.bufnr)) then
        stop_spinner(ctx)
        return
      end
      if not (ctx.spinner_timer and next(ctx.refreshing)) then
        return
      end
      ctx.spinner_frame = (ctx.spinner_frame or 0) + 1
      view.render_header(ctx)
      for name in pairs(ctx.refreshing) do
        view.render_row(ctx, name)
      end
    end)
  )
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
end

-- Apply one resolved plugin result into the report cache, then refresh just
-- that row in place. Each plugin flips from its spinner to its final status
-- independently, in completion order, with no full-table redraw.
local function apply_pipeline_result(ctx, result, counts)
  local name = result.name
  if result.status == "error" then
    state.pack_report_cache.plugins[name] = {
      status = "error",
      source = result.source,
      pending_updates = tostring(result.error or "refresh failed"),
    }
    counts.error = counts.error + 1
  else
    local prev = state.pack_report_cache.plugins[name]
    local entry = type(prev) == "table" and prev or {}
    entry.status = result.status
    entry.source = result.source
    entry.rev_before = result.rev_before
    entry.rev_after = result.rev_after
    -- Force re-inference of version/breaking/diff for the new revisions.
    entry.breaking = nil
    entry.diff_url = nil
    entry.current_version = nil
    entry.target_version = nil
    state.pack_report_cache.plugins[name] = entry
    counts[result.status] = (counts[result.status] or 0) + 1
  end

  ctx.refreshing[name] = nil

  -- Rebuild this one row from the updated cache and swap it into the visible
  -- table in place (line position is held stable during the refresh).
  local line_no = ctx.line_by_name and ctx.line_by_name[name]
  if line_no then
    local row = report.collect_dashboard_row(name)
    if row then
      ctx.row_by_line[line_no] = row
      for i, existing in ipairs(ctx.rows or {}) do
        if existing.name == name then
          ctx.rows[i] = row
          break
        end
      end
    end
  end
  view.render_row(ctx, name)
end

-- Resolve the set of plugin names a row op targets, mark them in-flight, and
-- return that resolved name list. `names` nil means every currently *visible*
-- row (used by the r/R refresh, which honors the active filter): the returned
-- list is then fed to the pipeline so the in-flight set, the progress
-- denominator, and the plugins actually refreshed are one and the same
-- population (otherwise a filtered r/R marked the 2 visible rows but the
-- nil-names pipeline scanned all managed plugins, yielding e.g. "status 79/2").
local function mark_targets(ctx, names)
  ctx.refreshing = {}
  local resolved = {}
  if names == nil then
    for _, row in ipairs(rows.visible(ctx)) do
      ctx.refreshing[row.name] = true
      resolved[#resolved + 1] = row.name
    end
  else
    for _, name in ipairs(names) do
      if type(name) == "string" and name ~= "" then
        ctx.refreshing[name] = true
        resolved[#resolved + 1] = name
      end
    end
  end
  return resolved
end

-- Drop a set of plugins from the cache + visible table (used by the clean
-- op, whose rows disappear rather than flip to a new status).
local function remove_rows(ctx, names)
  for _, name in ipairs(names) do
    if type(state.pack_report_cache.plugins) == "table" then
      state.pack_report_cache.plugins[name] = nil
    end
    ctx.selected[name] = nil
    ctx.refreshing[name] = nil
  end
end

-- Unified per-row operation engine. Every long-running dashboard mode routes
-- through here so the experience is identical: target rows immediately show an
-- inline spinner, an optional bulk mutation runs, then each row resolves
-- independently (flipping to its new status, or vanishing for removals) with a
-- single full re-render (re-sort + cursor + notify) at the very end.
--
-- spec fields:
--   names         list of target names, or nil for "all visible" (r/R)
--   online        whether the per-row status phase fetches before comparing
--   apply         optional fn() run once before the status phase (bulk mutate
--                 via vim.pack.update/del); blocking is fine, it is scheduled
--                 after the spinner paints
--   remove_on_done  true to delete target rows instead of re-evaluating them
--   on_finalize   optional fn(counts) run inside finalize, before the final
--                 render, for op-specific cache stamping / side effects
--   done_notify   optional fn(counts) run after the final render for the
--                 op-specific completion notice
--   per_row_apply optional fn(name) -> ok, err run for each plugin the moment
--                 its fetch/status resolves, BEFORE the row flips. Used by the
--                 update op to do a fast local (offline) checkout per plugin so
--                 the network fetch stays async (no UI freeze) and each row
--                 still flips independently. Only invoked for rows the pipeline
--                 resolved as "update"; on success the row is treated as
--                 up-to-date, on failure as an error row.
function M.run_row_op(ctx, spec)
  spec = spec or {}
  -- A row op is already in flight: the visible spinners already convey "busy",
  -- so silently ignore the repeat trigger instead of toasting.
  if ctx.online_check_running then
    return
  end
  ctx.online_check_running = true

  -- Refresh the row set from cache, mark targets in-flight, and render once so
  -- every target row shows its spinner immediately. `target_names` is the
  -- concrete list the op resolved (visible rows when spec.names is nil) and is
  -- what the pipeline scans, so the in-flight set and the progress denominator
  -- match what is actually refreshed.
  ctx.rows = report.collect_dashboard_rows()
  local target_names = mark_targets(ctx, spec.names)
  local total = vim.tbl_count(ctx.refreshing)
  ctx.online_check_progress = { phase = "status", done = 0, total = total }
  view.render(ctx)
  start_spinner(ctx)

  local current = rows.row_at_cursor(ctx)
  local current_name = current and current.name or nil
  local counts = { update = 0, same = 0, error = 0 }

  local function finalize()
    stop_spinner(ctx)
    ctx.refreshing = {}
    ctx.online_check_running = false
    ctx.online_check_progress = nil
    if spec.on_finalize then
      spec.on_finalize(counts)
    end
    state.write_persisted_state()
    M.update_after_scan(ctx, spec.online == true, counts, current_name, false)
    if spec.done_notify then
      spec.done_notify(counts)
    elseif counts.error > 0 then
      vim.notify(
        string.format("Plugin refresh failed for %d repo(s); see error rows", counts.error),
        vim.log.levels.WARN
      )
    end
  end

  -- The status phase resolves each target row independently. For removals we
  -- skip it: the rows just vanish at finalize.
  local function status_phase()
    if spec.remove_on_done then
      remove_rows(ctx, target_names)
      finalize()
      return
    end
    report.run_refresh_pipeline(target_names, spec.online == true, function(result, done_count)
      -- For the update op: now that this plugin's remote is fetched, perform a
      -- fast local checkout to the new revision, then present it as up-to-date.
      -- The slow fetch already happened asynchronously, so this stays snappy.
      if spec.per_row_apply and result.status == "update" then
        local ok, err = spec.per_row_apply(result.name)
        if ok then
          result.status = "same"
          result.rev_before = result.rev_after
        else
          result.status = "error"
          result.error = err or "checkout failed"
        end
      end
      apply_pipeline_result(ctx, result, counts)
      ctx.online_check_progress = { phase = "status", done = done_count, total = total }
      view.render_header(ctx)
    end, finalize)
  end

  -- Defer so the spinner render paints before any blocking bulk mutation runs.
  if spec.apply then
    vim.schedule(function()
      local ok, err = pcall(spec.apply)
      if not ok then
        stop_spinner(ctx)
        ctx.refreshing = {}
        ctx.online_check_running = false
        ctx.online_check_progress = nil
        vim.notify("Operation failed: " .. tostring(err), vim.log.levels.ERROR)
        ctx.rows = report.collect_dashboard_rows()
        view.render(ctx)
        return
      end
      status_phase()
    end)
  else
    status_phase()
  end
end

function M.refresh(ctx, next_online, names, merge, opts)
  opts = opts or {}
  local should_notify = opts.notify ~= false
  if opts.async then
    -- No start/result toasts: the dashboard itself shows per-row spinners and
    -- the header counters/stamps, so progress and outcome are already visible.
    -- Only genuine failures still surface (via finalize's default error warn).
    M.run_row_op(ctx, {
      names = names,
      online = next_online,
      on_finalize = function(counts)
        state.pack_report_cache.last_check_counts = counts
        state.pack_report_cache.mode = next_online and "online" or "offline"
        state.pack_report_cache.updated_at = os.time()
        if next_online and opts.mark_online then
          state.pack_report_cache.last_online_at = os.time()
        elseif (not next_online) and opts.mark_offline then
          state.pack_report_cache.last_offline_at = os.time()
        end
      end,
    })
    return
  end

  local current = rows.row_at_cursor(ctx)
  local current_name = current and current.name or nil
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
