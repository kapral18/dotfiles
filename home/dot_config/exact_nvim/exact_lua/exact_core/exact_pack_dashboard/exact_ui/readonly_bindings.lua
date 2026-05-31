local fmt = require("core.pack_dashboard.ui.format")
local rows = require("core.pack_dashboard.ui.rows")
local view = require("core.pack_dashboard.ui.view")
local popups = require("core.pack_dashboard.ui.popups")
local refresh = require("core.pack_dashboard.ui.refresh")
local operations = require("core.pack_dashboard.ui.operations")

local M = {}

local function cycle_filter_mode(ctx)
  for i, mode in ipairs(fmt.filter_modes) do
    if mode == ctx.filter_mode then
      ctx.filter_mode = fmt.filter_modes[(i % #fmt.filter_modes) + 1]
      return
    end
  end
  ctx.filter_mode = fmt.filter_modes[1]
end

local function close_dashboard(ctx)
  popups.close_details(ctx)
  if ctx.winid and vim.api.nvim_win_is_valid(ctx.winid) then
    pcall(vim.api.nvim_win_close, ctx.winid, true)
  else
    pcall(vim.api.nvim_buf_delete, ctx.bufnr, { force = true })
  end
end

local function toggle_current(ctx)
  local row = rows.row_at_cursor(ctx)
  if not row then
    return
  end
  ctx.selected[row.name] = not ctx.selected[row.name]
  view.render(ctx)
  refresh.persist_ui_state(ctx)
end

local function visual_toggle_selection(ctx)
  local start_line = vim.fn.line("v")
  local end_line = vim.fn.line(".")
  if start_line > end_line then
    start_line, end_line = end_line, start_line
  end
  local toggled = false
  for line = start_line, end_line do
    local row = ctx.row_by_line[line]
    if row then
      ctx.selected[row.name] = not ctx.selected[row.name]
      toggled = true
    end
  end
  vim.api.nvim_feedkeys(vim.api.nvim_replace_termcodes("<Esc>", true, false, true), "nx", false)
  if toggled then
    view.render(ctx)
    refresh.persist_ui_state(ctx)
  end
end

function M.attach(ctx)
  vim.keymap.set("n", "q", function()
    close_dashboard(ctx)
  end, { buffer = ctx.bufnr, nowait = true, silent = true })
  vim.keymap.set("n", "<Esc>", function()
    close_dashboard(ctx)
  end, { buffer = ctx.bufnr, nowait = true, silent = true })
  vim.keymap.set("n", "gg", function()
    if next(ctx.row_by_line) == nil then
      return
    end
    pcall(vim.api.nvim_win_set_cursor, 0, { ctx.first_data_line, 0 })
  end, { buffer = ctx.bufnr, nowait = true, silent = true })
  vim.keymap.set("n", "r", function()
    refresh.refresh(ctx, true, nil, nil, { mark_online = true, mark_offline = false, async = true })
  end, { buffer = ctx.bufnr, nowait = true, silent = true })
  vim.keymap.set("n", "R", function()
    refresh.refresh(ctx, false, nil, nil, { mark_online = false, mark_offline = true })
  end, { buffer = ctx.bufnr, nowait = true, silent = true })
  vim.keymap.set("n", "<Space>", function()
    toggle_current(ctx)
  end, { buffer = ctx.bufnr, nowait = true, silent = true })
  vim.keymap.set("n", "x", function()
    toggle_current(ctx)
  end, { buffer = ctx.bufnr, nowait = true, silent = true })
  vim.keymap.set("v", "<Space>", function()
    visual_toggle_selection(ctx)
  end, { buffer = ctx.bufnr, nowait = true, silent = true })
  vim.keymap.set("v", "x", function()
    visual_toggle_selection(ctx)
  end, { buffer = ctx.bufnr, nowait = true, silent = true })
  vim.keymap.set("n", "a", function()
    for _, row in ipairs(rows.visible(ctx)) do
      ctx.selected[row.name] = true
    end
    view.render(ctx)
    refresh.persist_ui_state(ctx)
  end, { buffer = ctx.bufnr, nowait = true, silent = true })
  vim.keymap.set("n", "A", function()
    ctx.selected = {}
    view.render(ctx)
    refresh.persist_ui_state(ctx)
  end, { buffer = ctx.bufnr, nowait = true, silent = true })
  vim.keymap.set("n", "<CR>", function()
    local row = rows.row_at_cursor(ctx)
    if row then
      operations.update_by_names(ctx, { row.name }, "No plugin on current row", "Plugin has no pending update")
    end
  end, { buffer = ctx.bufnr, nowait = true, silent = true })
  vim.keymap.set("n", "u", function()
    local names = rows.selected_names(ctx, true)
    if #names == 0 then
      local current = rows.row_at_cursor(ctx)
      if current then
        names = { current.name }
      end
    end
    operations.update_by_names(ctx, names, "No selected plugins", "No selected/cursor plugins have pending updates")
  end, { buffer = ctx.bufnr, nowait = true, silent = true })
  vim.keymap.set("n", "U", function()
    local names = {}
    for _, row in ipairs(rows.visible(ctx)) do
      names[#names + 1] = row.name
    end
    operations.update_by_names(ctx, names, "No visible plugins to update", "No visible plugins have pending updates")
  end, { buffer = ctx.bufnr, nowait = true, silent = true })
  vim.keymap.set("n", "C", function()
    local orphans, selected_orphans = {}, {}
    for _, row in ipairs(ctx.rows) do
      if row.is_orphan then
        orphans[#orphans + 1] = row.name
        if ctx.selected[row.name] then
          selected_orphans[#selected_orphans + 1] = row.name
        end
      end
    end
    operations.clean_orphan_rows(
      ctx,
      #selected_orphans > 0 and selected_orphans or orphans,
      #selected_orphans > 0 and "selected" or "all"
    )
  end, { buffer = ctx.bufnr, nowait = true, silent = true })
  vim.keymap.set("n", "V", function()
    local drifted, selected_drifted = {}, {}
    for _, row in ipairs(ctx.rows) do
      if row.is_drift then
        drifted[#drifted + 1] = row.name
        if ctx.selected[row.name] then
          selected_drifted[#selected_drifted + 1] = row.name
        end
      end
    end
    operations.heal_drift_rows(ctx, #selected_drifted > 0 and selected_drifted or drifted)
  end, { buffer = ctx.bufnr, nowait = true, silent = true })
  vim.keymap.set("n", "o", function()
    operations.open_diff_or_repo_for_row(rows.row_at_cursor(ctx))
  end, { buffer = ctx.bufnr, nowait = true, silent = true })
  vim.keymap.set("n", "O", function()
    local row = rows.row_at_cursor(ctx)
    if not row or not row.repo_url then
      vim.notify("No repo URL for this plugin", vim.log.levels.WARN)
      return
    end
    vim.ui.open(row.repo_url)
  end, { buffer = ctx.bufnr, nowait = true, silent = true })
  vim.keymap.set("n", "K", function()
    popups.open_details(ctx, rows.row_at_cursor(ctx))
  end, { buffer = ctx.bufnr, nowait = true, silent = true })
  vim.keymap.set("n", "T", function()
    local row = rows.row_at_cursor(ctx)
    if row and row.name then
      vim.api.nvim_cmd({ cmd = "PackTrace", args = { row.name } }, {})
      return
    end
    vim.api.nvim_cmd({ cmd = "PackTrace" }, {})
  end, { buffer = ctx.bufnr, nowait = true, silent = true })
  vim.keymap.set("n", "f", function()
    cycle_filter_mode(ctx)
    view.render(ctx)
    refresh.persist_ui_state(ctx)
  end, { buffer = ctx.bufnr, nowait = true, silent = true })
  vim.keymap.set("n", "s", function()
    ctx.sort_mode = ctx.sort_mode == "status" and "name" or "status"
    view.render(ctx)
    refresh.persist_ui_state(ctx)
  end, { buffer = ctx.bufnr, nowait = true, silent = true })
  vim.keymap.set("n", "/", function()
    vim.ui.input({ prompt = "Plugin search (name substring): ", default = ctx.search_text or "" }, function(input)
      if input == nil then
        return
      end
      local normalized = vim.trim(input)
      ctx.search_text = normalized ~= "" and normalized or nil
      if ctx.winid and vim.api.nvim_win_is_valid(ctx.winid) then
        vim.api.nvim_set_current_win(ctx.winid)
      end
      view.render(ctx)
      refresh.persist_ui_state(ctx)
    end)
  end, { buffer = ctx.bufnr, nowait = true, silent = true })
  vim.keymap.set("n", "c", function()
    ctx.search_text = nil
    view.render(ctx)
    refresh.persist_ui_state(ctx)
  end, { buffer = ctx.bufnr, nowait = true, silent = true })
  vim.keymap.set("n", "?", popups.open_help, { buffer = ctx.bufnr, nowait = true, silent = true })
end

return M
