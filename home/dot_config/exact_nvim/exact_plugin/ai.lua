_G.myfuncs = _G.myfuncs or {}
_G.myfuncs.execute_my_command = function()
  local prompt = "Give me commit message summary from git diff output above using conventional commits format."
  local command = "git diff --cached | chatblade -c gpt-4o -e " .. vim.fn.shellescape(prompt)
  local output = vim.fn.systemlist(command)
  local win = vim.api.nvim_get_current_win()
  local cursor = vim.api.nvim_win_get_cursor(win)
  for _, line in ipairs(output) do
    vim.api.nvim_buf_set_lines(0, cursor[1] - 1, cursor[1] - 1, false, { line })
    cursor[1] = cursor[1] + 1
  end
end

vim.api.nvim_set_keymap("n", "<leader>aid", ":lua _G.myfuncs.execute_my_command()<CR>", { noremap = true })
