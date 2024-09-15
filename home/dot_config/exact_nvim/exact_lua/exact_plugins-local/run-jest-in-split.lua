local M = {}

M.get_current_test_name = function()
  local current_line = vim.api.nvim_get_current_line()
  local test_name = current_line:match("[\"'](.-)[\"']")
  return test_name
end

M.run_jest_test = function(test_name)
  local cmd = "node scripts/jest " .. vim.fn.expand("%") .. " -t '" .. test_name .. "'"

  vim.cmd.vsplit()
  vim.cmd.terminal()
  vim.api.nvim_chan_send(vim.bo.channel, cmd .. "\n")
end

M.run_jest_in_split = function()
  local test_name = M.get_current_test_name()
  if test_name then
    M.run_jest_test(test_name)
  else
    print("No test name found on the current line.")
  end
end

M.close_terminal_buffer = function()
  local buf = vim.api.nvim_get_current_buf()

  if vim.bo[buf].buftype ~= "terminal" then
    print("This is not a terminal buffer.")
    return
  end

  local chan = vim.bo[buf].channel

  vim.fn.jobstop(chan)

  vim.cmd("bdelete! " .. buf)
end

return M
