local M = {}

M.match_test_name_from_line = function(line)
  local testNamePatterns = {
    "it%(",
    "test%(",
    "describe%(",
  }

  local quotePatterns = {
    '"',
    "'",
    "`",
  }

  for _, testNamePattern in ipairs(testNamePatterns) do
    for _, quotePattern in ipairs(quotePatterns) do
      local test_name = string.match(line, "^%s.*" .. testNamePattern .. quotePattern .. "(.-)" .. quotePattern)
      if test_name then
        return test_name
      end
    end
  end
end

M.get_current_test_name = function()
  local current_line = vim.api.nvim_get_current_line()
  local current_line_test_name = M.match_test_name_from_line(current_line)

  if current_line_test_name then
    return current_line_test_name
  end

  local current_line_number = vim.api.nvim_win_get_cursor(0)[1]
  local lines_from_top_to_current = vim.api.nvim_buf_get_lines(0, 0, current_line_number - 1, false)

  local enclosing_test_name = nil
  for i = #lines_from_top_to_current, 1, -1 do
    local line = lines_from_top_to_current[i]
    local matched_enclosing_test_name = M.match_test_name_from_line(line)
    if matched_enclosing_test_name then
      enclosing_test_name = matched_enclosing_test_name
      break
    end
  end

  return enclosing_test_name
end

M.escape_shell_arg = function(str)
  str = str:gsub("'", "\\'")
  str = str:gsub('"', '\\"')
  str = str:gsub("`", "\\`")
  return "'" .. str .. "'"
end

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

M.run_jest_in_split = function()
  M.close_terminal_buffer()
  local test_name = M.get_current_test_name()
  if test_name then
    local escaped_test_name = M.escape_shell_arg(test_name)
    local arg = " -t " .. escaped_test_name
    M.run_jest_cmd(arg)
  else
    M.run_jest_cmd()
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
