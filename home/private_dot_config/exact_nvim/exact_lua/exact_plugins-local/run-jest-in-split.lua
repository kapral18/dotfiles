local testNamePatterns = {
  it = "it%(",
  test = "test%(",
  describe = "describe%(",
}

local quotePatterns = {
  '"',
  "'",
  "`",
}

local M = {}

M.match_test_name_from_line = function(line)
  for test_type, testNamePattern in pairs(testNamePatterns) do
    for _, quotePattern in ipairs(quotePatterns) do
      local test_name = string.match(line, "^%s*" .. testNamePattern .. quotePattern .. "(.-)" .. quotePattern)
      if test_name then
        return test_name, test_type
      end
    end
  end
end

M.get_current_test_name = function()
  local current_line = vim.api.nvim_get_current_line()
  local current_line_test_name, current_line_test_type = M.match_test_name_from_line(current_line)

  if current_line_test_name then
    return current_line_test_name, current_line_test_type
  end

  local current_line_number = vim.api.nvim_win_get_cursor(0)[1]
  local lines_from_top_to_current = vim.api.nvim_buf_get_lines(0, 0, current_line_number - 1, false)

  local enclosing_test_name = nil
  local enclosing_test_type = nil
  for i = #lines_from_top_to_current, 1, -1 do
    local line = lines_from_top_to_current[i]
    local matched_enclosing_test_name, matched_enclosing_test_type = M.match_test_name_from_line(line)
    if matched_enclosing_test_name then
      enclosing_test_name = matched_enclosing_test_name
      enclosing_test_type = matched_enclosing_test_type
      break
    end
  end

  return enclosing_test_name, enclosing_test_type
end

---@param str string
M.escape_shell_arg = function(str)
  str = str:gsub("'", "\\'")
  str = str:gsub('"', '\\"')
  str = str:gsub("`", "\\`")
  str = str:gsub("%$", "\\$")
  str = str:gsub("%^", "\\^")
  str = str:gsub("%*", "\\*")
  str = str:gsub("%+", "\\+")
  str = str:gsub("%?", "\\?")
  str = str:gsub("%[", "\\[")
  str = str:gsub("%]", "\\]")
  str = str:gsub("%{", "\\{")
  str = str:gsub("%}", "\\}")
  str = str:gsub("%(", "\\(")
  str = str:gsub("%)", "\\)")
  str = str:gsub("%|", "\\|")
  return str
end

---@param arg? string
M.run_jest_cmd = function(arg)
  local cmd = "node scripts/jest " .. vim.fn.expand("%")

  if arg then
    cmd = cmd .. " " .. arg
  end

  local original_win = vim.api.nvim_get_current_win()

  vim.cmd.vsplit()
  vim.cmd.terminal()
  vim.api.nvim_chan_send(vim.bo.channel, cmd .. "\n")

  -- Return focus to the original window
  vim.api.nvim_set_current_win(original_win)
end

---@param options? {update_snapshots?: boolean, entire_file?: boolean}
M.run_jest_in_split = function(options)
  options = options or {}
  local update_snapshots = options.update_snapshots or false
  local entireFile = options.entire_file or false

  M.close_terminal_buffer()

  local update_snapshots_arg = update_snapshots and " --updateSnapshot" or nil

  if entireFile then
    M.run_jest_cmd(update_snapshots_arg)
  else
    local test_name, test_type = M.get_current_test_name()

    if test_name then
      local escaped_test_name = "'" .. M.escape_shell_arg(test_name) .. (test_type == "describe" and "" or "$") .. "'"
      local arg = " -t " .. escaped_test_name
      if update_snapshots_arg then
        arg = arg .. update_snapshots_arg
      end
      M.run_jest_cmd(arg)
    else
      M.run_jest_cmd(update_snapshots_arg)
    end
  end
end

M.close_terminal_buffer = function()
  local buf = vim.api.nvim_get_current_buf()

  if vim.bo[buf].buftype ~= "terminal" then
    local term_buf = nil

    for _, b in ipairs(vim.api.nvim_list_bufs()) do
      if vim.bo[b].buftype == "terminal" then
        term_buf = b
        buf = b
        break
      end
    end

    if not term_buf then
      return
    end
  end

  local chan = vim.bo[buf].channel

  vim.fn.jobstop(chan)

  vim.cmd("bdelete! " .. buf)
end

return M
