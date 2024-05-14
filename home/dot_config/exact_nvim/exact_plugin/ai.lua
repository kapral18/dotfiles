_G.myfuncs = _G.myfuncs or {}
_G.myfuncs.execute_my_command = function()
  local prompt =
    "Give me commit message summary from git diff output above. Keep it concise without detail loss. Use conventional-commits message format."
  vim.cmd(":r! git diff --cached | chatblade -c gpt-4o -e '" .. vim.fn.shellescape(prompt) .. "'")
end

vim.api.nvim_set_keymap("n", "<leader>aid", ":lua _G.myfuncs.execute_my_command()<CR>", { noremap = true })
