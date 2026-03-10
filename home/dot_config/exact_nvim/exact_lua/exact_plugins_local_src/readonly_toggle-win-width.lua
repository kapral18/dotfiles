local prev_widths = {}

local MIN_WIDTH = 10
local MAX_WIDTH = 300

local M = {}

M.toggle_win_width = function()
  local win_id = vim.api.nvim_get_current_win()

  for id in pairs(prev_widths) do
    if not vim.api.nvim_win_is_valid(id) then
      prev_widths[id] = nil
    end
  end

  if prev_widths[win_id] then
    vim.api.nvim_win_set_width(win_id, prev_widths[win_id])
    prev_widths[win_id] = nil
  else
    local buf_id = vim.api.nvim_win_get_buf(win_id)
    local width = vim.api.nvim_win_get_width(win_id)
    prev_widths[win_id] = width

    local lines = vim.api.nvim_buf_get_lines(buf_id, 0, -1, false)

    local max_length = 0
    for _, line in ipairs(lines) do
      max_length = math.max(max_length, vim.fn.strdisplaywidth(line))
    end

    max_length = math.max(MIN_WIDTH, math.min(MAX_WIDTH, max_length))
    vim.api.nvim_win_set_width(win_id, max_length)
  end
end

return M
