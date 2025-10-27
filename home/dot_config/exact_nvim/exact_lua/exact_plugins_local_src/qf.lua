local util = require("util")

local function extract_path_from_text(text)
  local trimmed = text:match("^%s*(.-)%s*$") or ""
  if trimmed == "" then
    return nil
  end

  if trimmed:match("^%a:[/\\]") then
    -- Windows-style absolute path
    local win_path = trimmed:match("^(%a:[/\\].-):%d+")
      or trimmed:match("^(%a:[/\\].-):%d+:%d+")
      or trimmed
    return win_path
  end

  return trimmed:match("^(.-):%d+:%d+:")
    or trimmed:match("^(.-):%d+:%d+")
    or trimmed:match("^(.-):%d+")
    or trimmed
end

local function extract_path_from_item(item, base_dir)
  if item.filename and item.filename ~= "" then
    return util.normalize_path(item.filename, base_dir)
  end

  if
    item.bufnr
    and item.bufnr > 0
    and vim.api.nvim_buf_is_valid(item.bufnr)
  then
    local name = vim.api.nvim_buf_get_name(item.bufnr)
    if name and name ~= "" then
      return util.normalize_path(name, base_dir)
    end
  end

  if item.text and item.text ~= "" then
    local candidate = extract_path_from_text(item.text)
    if candidate then
      return util.normalize_path(candidate, base_dir)
    end
  end

  return nil
end

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
  local qfall = vim.fn.getqflist()

  if #qfall == 0 then
    vim.notify("Quickfix list is empty", vim.log.levels.WARN)
    return
  end

  local curqfidx = vim.fn.line(".")

  if curqfidx < 1 or curqfidx > #qfall then
    vim.notify("Invalid quickfix index", vim.log.levels.ERROR)
    return
  end

  table.remove(qfall, curqfidx)
  vim.fn.setqflist(qfall, "r")

  local new_idx = curqfidx <= #qfall and curqfidx or math.max(curqfidx - 1, 1)

  if new_idx > 0 then
    vim.api.nvim_win_set_cursor(0, { new_idx, 0 })
  end
end

function M.copy_qf_paths_to_clipboard()
  local info = vim.fn.getqflist({ items = 1 })
  local items = info.items or {}
  local base_dir = info.directory

  local paths = {}
  local seen = {}

  for _, item in ipairs(items) do
    local path = extract_path_from_item(item, base_dir)

    if path and not seen[path] then
      seen[path] = true
      table.insert(paths, path)
    end
  end

  if #paths > 0 then
    util.copy_to_clipboard(table.concat(paths, "\n"))
  end
end

function M.dedupe_qf_by_path()
  local info = vim.fn.getqflist({ items = 1 })
  local items = info.items or {}
  local base_dir = info.directory

  local seen = {}
  local deduped = {}

  for _, item in ipairs(items) do
    local path = extract_path_from_item(item, base_dir)

    if path and not seen[path] then
      seen[path] = true
      table.insert(deduped, item)
    end
  end

  vim.fn.setqflist(deduped, "r")
  vim.notify(
    string.format("Deduped: %d → %d items", #items, #deduped),
    vim.log.levels.INFO
  )
end

return M
