_G.myfuncs = _G.myfuncs or {}
_G.myfuncs.execute_my_command = function()
  local prompt = [[
  Summarize git diff output given above as a commit. 
  Each line should be max 70 characters long. 

  Give me only the commit text.
  Format commit message using conventional commits. 

  Example:

  feat: add new feature

  - detail one
  - detail two
  - detail three
  ...
  ]]
  vim.cmd(":r! git diff --cached | chatblade -e '" .. vim.fn.shellescape(prompt) .. "'")
end

vim.api.nvim_set_keymap("n", "<leader>aid", ":lua _G.myfuncs.execute_my_command()<CR>", { noremap = true })
