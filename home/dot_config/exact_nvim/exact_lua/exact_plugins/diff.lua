local augrp = vim.api.nvim_create_augroup
local aucmd = vim.api.nvim_create_autocmd

augrp("k18", {})

return {
  {

    "AndrewRadev/linediff.vim",
    config = function()
      aucmd({ "WinEnter", "BufEnter" }, {
        group = "k18",
        pattern = "*",
        callback = function()
          -- Check if the current window has the 'diff' option set
          if vim.wo.diff then
            -- Map 'q' to call ':LinediffReset' in normal mode, buffer-local
            vim.keymap.set("n", "q", ":LinediffReset<CR>", { buffer = true, desc = "Reset linediff" })
          end
        end,
      })
    end,
  },
}
