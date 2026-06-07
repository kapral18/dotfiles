local state = require("core.pack_dashboard.state")
local analysis = require("core.pack_dashboard.analysis")
local report = require("core.pack_dashboard.report")
local view = require("core.pack_dashboard.ui.view")
local bindings = require("core.pack_dashboard.ui.bindings")
local refresh = require("core.pack_dashboard.ui.refresh")

local M = {}

-- Module-level singleton ref so repeated `:PackDashboard` calls reuse the same
-- floating window instead of stacking instances. Cleared by the WinClosed autocmd.
local dashboard_winid = nil

local function create_dashboard_buffer()
  local bufnr = vim.api.nvim_create_buf(false, true)
  vim.bo[bufnr].buftype = "nofile"
  vim.bo[bufnr].bufhidden = "wipe"
  vim.bo[bufnr].buflisted = false
  vim.bo[bufnr].swapfile = false
  vim.bo[bufnr].modifiable = true
  vim.bo[bufnr].filetype = "packdashboard"
  return bufnr
end

local function open_popup_window(ctx)
  local total_lines = vim.o.lines - vim.o.cmdheight
  local width_ratio = math.max(0.45, math.min(0.98, tonumber(vim.g.pack_dashboard_width_ratio) or 0.68))
  local height_ratio = math.max(0.45, math.min(0.98, tonumber(vim.g.pack_dashboard_height_ratio) or 0.68))
  local min_width = tonumber(vim.g.pack_dashboard_min_width) or 84
  local min_height = tonumber(vim.g.pack_dashboard_min_height) or 18
  local margin = math.max(2, tonumber(vim.g.pack_dashboard_margin) or 6)

  local width = math.min(math.max(min_width, math.floor(vim.o.columns * width_ratio)), vim.o.columns - margin)
  local height = math.min(math.max(min_height, math.floor(total_lines * height_ratio)), total_lines - margin)
  local row = math.floor((total_lines - height) / 2)
  local col = math.floor((vim.o.columns - width) / 2)

  ctx.winid = vim.api.nvim_open_win(ctx.bufnr, true, {
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

  vim.wo[ctx.winid].number = false
  vim.wo[ctx.winid].relativenumber = false
  vim.wo[ctx.winid].signcolumn = "no"
  vim.wo[ctx.winid].foldcolumn = "0"
  vim.wo[ctx.winid].wrap = false
  vim.wo[ctx.winid].cursorline = false
  vim.wo[ctx.winid].smoothscroll = false

  dashboard_winid = ctx.winid
  vim.api.nvim_create_autocmd("WinClosed", {
    once = true,
    pattern = tostring(ctx.winid),
    callback = function()
      if dashboard_winid == ctx.winid then
        dashboard_winid = nil
      end
    end,
  })
end

function M.open(online, force_scan)
  if dashboard_winid and vim.api.nvim_win_is_valid(dashboard_winid) then
    if force_scan then
      pcall(vim.api.nvim_win_close, dashboard_winid, true)
      dashboard_winid = nil
    else
      pcall(vim.api.nvim_set_current_win, dashboard_winid)
      return
    end
  end

  if not report.ensure_dashboard_cache(online, force_scan) then
    return
  end

  local ctx = view.new_context({
    bufnr = create_dashboard_buffer(),
    rows = report.collect_dashboard_rows(),
    selected = {},
    filter_mode = state.dashboard_ui_cache.filter_mode or "all",
    sort_mode = state.dashboard_ui_cache.sort_mode or "status",
    search_text = state.dashboard_ui_cache.search_text,
  })
  for _, name in ipairs(state.dashboard_ui_cache.selected_names or {}) do
    ctx.selected[name] = true
  end

  open_popup_window(ctx)
  bindings.attach(ctx)
  view.render(ctx)
  analysis.refresh_version_flags_async(function()
    -- Skip the standalone re-render while an online refresh is in flight; its
    -- finalize re-collects rows (with the now-populated flags) and re-renders.
    if ctx.online_check_running then
      return
    end
    ctx.rows = report.collect_dashboard_rows()
    view.render(ctx)
  end)
  -- Always start with a fresh online status check on open: each row arrives
  -- independently via the unified per-row pipeline (same as pressing `R`).
  if vim.g.pack_dashboard_refresh_on_open ~= false then
    refresh.refresh(ctx, true, nil, nil, { mark_online = true, mark_offline = false, async = true })
  end
end

return M
