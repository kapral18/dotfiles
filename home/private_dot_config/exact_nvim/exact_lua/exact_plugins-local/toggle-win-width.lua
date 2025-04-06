local prev_widths = {}

local M = {}

M.toggle_win_width = function()
  local win_id = vim.api.nvim_get_current_win()
  local buf_id = vim.api.nvim_win_get_buf(win_id)
  local width = vim.api.nvim_win_get_width(win_id)

  if prev_widths[win_id] then
    -- Restore the previous width
    vim.api.nvim_win_set_width(win_id, prev_widths[win_id])
    prev_widths[win_id] = nil
  else
    -- Save the current width
    prev_widths[win_id] = width

    -- Get all lines in the buffer
    local lines = vim.api.nvim_buf_get_lines(buf_id, 0, -1, false)

    -- Find the length of the longest line
    local max_length = 0
    for _, line in ipairs(lines) do
      local length = #line
      if length > max_length then
        max_length = length
      end
    end

    -- Resize the window to the width of the longest line
    vim.api.nvim_win_set_width(win_id, max_length)
  end
end

return M
