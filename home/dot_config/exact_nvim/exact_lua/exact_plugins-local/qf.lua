local M = {}

-- Helper function to filter quickfix items by pattern
---@param pattern string
---@param exclude? boolean - exclude items that match the pattern
---@return nil
function M.filter_qf_items_by_pattern(pattern, exclude)
  -- Get the current quickfix list
  local qf_list = vim.fn.getqflist()

  -- Create a Vim regex object from the pattern
  local regex = vim.regex(pattern)

  -- Filter out items where the text matches the pattern
  local new_list = vim.tbl_filter(function(item)
    local match = regex:match_str(item.text)
    if exclude then
      return not match
    end
    return match and true or false
  end, qf_list)

  -- Set the new quickfix list with the filtered items and preserved title
  vim.fn.setqflist(new_list, "r")
end

function M.remove_qf_item()
  local curqfidx = vim.fn.line(".")
  local qfall = vim.fn.getqflist()

  -- Return if there are no items to remove
  if #qfall == 0 then
    return
  end

  -- Remove the item from the quickfix list
  table.remove(qfall, curqfidx)
  vim.fn.setqflist(qfall, "r")

  -- If not at the end of the list, stay at the same index, otherwise, go one up
  local new_idx = curqfidx <= #qfall and curqfidx or math.max(curqfidx - 1, 1)

  -- Set the cursor position directly in the quickfix window
  vim.api.nvim_win_set_cursor(0, { new_idx, 0 })
end

return M
