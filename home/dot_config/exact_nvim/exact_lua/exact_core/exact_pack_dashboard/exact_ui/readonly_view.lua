local fmt = require("core.pack_dashboard.ui.format")
local render = require("core.pack_dashboard.ui.render")

local M = {}

function M.new_context(opts)
  local use_nerd_font = vim.g.pack_dashboard_ascii ~= true
  local icons = fmt.icons(use_nerd_font)
  return vim.tbl_extend("force", opts or {}, {
    use_nerd_font = use_nerd_font,
    fast_scroll_mode = vim.g.pack_dashboard_fast_scroll ~= false,
    icons = icons,
    status_icon = fmt.status_icons(icons),
    row_by_line = {},
    line_by_name = {},
    first_data_line = 1,
    online_check_running = false,
    online_check_progress = nil,
    refreshing = {},
    spinner_frame = 0,
    spinner_frames = fmt.spinner_frames(use_nerd_font),
    details_winid = nil,
    details_bufnr = nil,
  })
end

function M.render(ctx)
  render.render(ctx)
end

function M.render_row(ctx, name)
  render.render_row(ctx, name)
end

function M.render_header(ctx)
  render.render_header(ctx)
end

return M
