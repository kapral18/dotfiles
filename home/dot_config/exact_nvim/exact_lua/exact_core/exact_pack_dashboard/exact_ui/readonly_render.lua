local state = require("core.pack_dashboard.state")
local fmt = require("core.pack_dashboard.ui.format")
local rows = require("core.pack_dashboard.ui.rows")

local M = {}

local dashboard_ns = vim.api.nvim_create_namespace("core.pack_dashboard")

local function ensure_highlights()
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
  set_hl(0, "PackDashboardStatusDrift", { default = true, link = "DiagnosticWarn" })
  set_hl(0, "PackDashboardStatusRisky", { default = true, link = "DiagnosticWarn" })
  set_hl(0, "PackDashboardRiskBreak", { default = true, link = "DiagnosticWarn" })
  set_hl(0, "PackDashboardRiskSafe", { default = true, link = "DiffAdd" })
  set_hl(0, "PackDashboardRiskUnknown", { default = true, link = "Comment" })
  set_hl(0, "PackDashboardLink", { default = true, link = "Underlined" })
  set_hl(0, "PackDashboardSelected", { default = true, link = "IncSearch" })
end

local function raw_status_line(ctx)
  local raw = state.pack_report_cache.last_check_counts
  local line = "last-result raw: n/a (run r for online check)"
  if type(raw) == "table" then
    line = string.format(
      "last-result raw: update:%d same:%d error:%d",
      tonumber(raw.update) or 0,
      tonumber(raw.same) or 0,
      tonumber(raw.error) or 0
    )
  end
  line = string.format(
    "%s   online:%s   offline:%s",
    line,
    state.format_cache_stamp(state.pack_report_cache.last_online_at),
    state.format_cache_stamp(state.pack_report_cache.last_offline_at)
  )
  if ctx.online_check_running then
    local progress = ctx.online_check_progress
    if type(progress) == "table" and progress.phase == "status" then
      line = line .. "   check:status"
    elseif type(progress) == "table" and tonumber(progress.total) and progress.total > 0 then
      line = line .. string.format("   check:fetch:%d/%d", tonumber(progress.done) or 0, progress.total)
    else
      line = line .. "   check:fetch:start"
    end
  end
  return line
end

local function stats_line(ctx, counts)
  if ctx.use_nerd_font then
    return string.format(
      "%s %d   %s %d   %s %d   %s %d   %s %d   %s %d   %s %d   %s %d",
      ctx.icons.update,
      counts.update,
      ctx.icons.same,
      counts.same,
      ctx.icons.error,
      counts.error,
      ctx.icons.unknown,
      counts.unknown,
      ctx.icons.orphan,
      counts.orphan,
      ctx.icons.drift,
      counts.drift,
      ctx.icons.risky,
      counts.risky,
      ctx.icons.risk_break,
      counts.breaking
    )
  end
  return string.format(
    "updates:%d  same:%d  errors:%d  unknown:%d  orphan:%d  drift:%d  risky:%d  breaking:%d",
    counts.update,
    counts.same,
    counts.error,
    counts.unknown,
    counts.orphan,
    counts.drift,
    counts.risky,
    counts.breaking
  )
end

local function build_lines(ctx)
  local counts = rows.summary_counts(ctx)
  local visible = rows.visible(ctx)
  local sel_visible = rows.selected_count(ctx, true)
  local sel_total = rows.selected_count(ctx, false)
  local title = ctx.use_nerd_font and "󰒲  vim.pack dashboard" or "vim.pack dashboard"
  local win_width = (ctx.winid and vim.api.nvim_win_is_valid(ctx.winid)) and vim.api.nvim_win_get_width(ctx.winid)
    or vim.o.columns
  local row_width = math.max(80, win_width - 2)
  local sep = string.rep(ctx.use_nerd_font and "─" or "-", row_width)
  local name_col, version_col, links_col = 34, 26, 12

  local lines = {
    string.format(
      "%s   mode:%s   result:%s   applied:%s (%d)   selected:%d/%d",
      title,
      state.pack_report_cache.mode or "unknown",
      state.format_cache_stamp(state.pack_report_cache.updated_at),
      state.format_cache_stamp(state.pack_report_cache.last_applied_at),
      tonumber(state.pack_report_cache.last_applied_count) or 0,
      sel_visible,
      sel_total
    ),
    stats_line(ctx, counts),
    raw_status_line(ctx),
    string.format(
      "r online-refresh  R offline-status  <CR>/u/U update-pending  C clean-orphans  V heal-drift  f filter:%s  s sort:%s  / search:%s  a sel-all  o link  K details  ? help",
      ctx.filter_mode,
      ctx.sort_mode,
      ctx.search_text or "-"
    ),
    sep,
    table.concat({
      fmt.pad_cell("SEL", 3),
      fmt.pad_cell("ST", 2),
      fmt.pad_cell("RK", 2),
      fmt.pad_cell("PLUGIN", name_col),
      fmt.pad_cell("VERSION", version_col),
      fmt.pad_cell("LINKS", links_col),
    }, " "),
    sep,
  }

  ctx.row_by_line = {}
  ctx.first_data_line = #lines + 1
  for _, row in ipairs(visible) do
    lines[#lines + 1] = table.concat({
      fmt.pad_cell(ctx.selected[row.name] and "[x]" or "[ ]", 3),
      fmt.pad_cell(ctx.status_icon[row.status] or "?", 2),
      fmt.pad_cell(fmt.risk_label(ctx, row), 2),
      fmt.pad_cell(row.name, name_col),
      fmt.pad_cell(fmt.version_cell(row), version_col),
      fmt.pad_cell(fmt.links_cell(ctx, row), links_col),
    }, " ")
    ctx.row_by_line[#lines] = row
  end
  if #visible == 0 then
    lines[#lines + 1] = "(No plugins match current filter/search)"
  end
  return lines
end

local function highlight_static_headers(bufnr, lines)
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
end

local function highlight_rows(ctx)
  local row_count = 0
  for _ in pairs(ctx.row_by_line) do
    row_count = row_count + 1
  end
  if ctx.fast_scroll_mode and row_count > 120 then
    return
  end

  local status_hl = {
    update = "PackDashboardStatusUpdate",
    same = "PackDashboardStatusSame",
    error = "PackDashboardStatusError",
    unknown = "PackDashboardStatusUnknown",
    orphan = "PackDashboardStatusOrphan",
    drift = "PackDashboardStatusDrift",
    risky = "PackDashboardStatusRisky",
  }
  local sel_start, sel_end = 0, 3
  local st_start = sel_end + 1
  local st_end = st_start + (ctx.use_nerd_font and 3 or 1) + 1
  local rk_start = st_end + 1
  local rk_end = rk_start + 2

  for line_no, row in pairs(ctx.row_by_line) do
    if ctx.selected[row.name] then
      pcall(vim.api.nvim_buf_set_extmark, ctx.bufnr, dashboard_ns, line_no - 1, sel_start, {
        hl_group = "PackDashboardSelected",
        end_col = sel_end,
      })
    end
    pcall(vim.api.nvim_buf_set_extmark, ctx.bufnr, dashboard_ns, line_no - 1, st_start, {
      hl_group = status_hl[row.status] or "PackDashboardStatusUnknown",
      end_col = st_end,
    })
    if row.status == "update" then
      local risk_group = row.breaking == true and "PackDashboardRiskBreak"
        or (row.breaking == false and "PackDashboardRiskSafe" or "PackDashboardRiskUnknown")
      pcall(vim.api.nvim_buf_set_extmark, ctx.bufnr, dashboard_ns, line_no - 1, rk_start, {
        hl_group = risk_group,
        end_col = rk_end,
      })
    end
  end
end

function M.render(ctx)
  if not vim.api.nvim_buf_is_valid(ctx.bufnr) then
    return
  end
  ensure_highlights()
  local lines = build_lines(ctx)
  vim.bo[ctx.bufnr].modifiable = true
  vim.api.nvim_buf_set_lines(ctx.bufnr, 0, -1, false, lines)
  vim.bo[ctx.bufnr].modifiable = false
  vim.api.nvim_buf_clear_namespace(ctx.bufnr, dashboard_ns, 0, -1)
  highlight_static_headers(ctx.bufnr, lines)
  highlight_rows(ctx)
end

return M
