local function get_current_test_name()
  local current_line = vim.api.nvim_get_current_line()
  local test_name = current_line:match("[\"'](.-)[\"']")
  return test_name
end

local function run_jest_test(test_name)
  local cmd = "node scripts/jest " .. vim.fn.expand("%") .. " -t '" .. test_name .. "'"

  vim.cmd.vsplit()
  vim.cmd.terminal()
  vim.api.nvim_chan_send(vim.bo.channel, cmd .. "\n")
end

local function run_current_test()
  local test_name = get_current_test_name()
  if test_name then
    run_jest_test(test_name)
  else
    print("No test name found on the current line.")
  end
end

vim.keymap.set("n", "<Leader>tx", run_current_test, { noremap = true, silent = true })
