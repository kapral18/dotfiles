vim.api.nvim_set_keymap("n", "<leader>aid", ":lua execute_my_command()<CR>", { noremap = true })

function execute_my_command()
  vim.cmd(
    ':r! git diff --cached | chatblade -e "Summarize above given git diff as a commit. Each line should be max 70 characters long. Give me only the commit text."'
  )
end
