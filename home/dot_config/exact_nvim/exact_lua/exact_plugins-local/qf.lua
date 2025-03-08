local M = {}

-- Helper function to filter quickfix items by pattern
---@param pattern string
---@param exclude? boolean - exclude items that match the pattern
---@return nil
M.filter_qf_items_by_pattern = function(pattern, exclude)
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

return M
