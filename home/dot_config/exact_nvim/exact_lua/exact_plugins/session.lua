return {
  {
    "folke/persistence.nvim",
    enabled = false,
  },
  {
    "rmagatti/auto-session",
    lazy = false,
    dependencies = {
      { "nvim-telescope/telescope.nvim", opt = true },
    },
    keys = {
      { "<localleader>ss", "<cmd>SessionSave<CR>", desc = "Save session" },
    },
    ---enables autocomplete for opts
    ---@module "auto-session"
    ---@type AutoSession.Config
    opts = {
      suppressed_dirs = { "~/", "~/code", "~/Downloads", "/" },
      pre_save_cmds = {
        "tabdo Neotree close",
      },

      -- Save quickfix list and open it when restoring the session
      save_extra_cmds = {
        function()
          local qflist = vim.fn.getqflist()
          -- return nil to clear any old qflist
          if #qflist == 0 then
            return nil
          end
          local qfinfo = vim.fn.getqflist({ title = 1 })

          for _, entry in ipairs(qflist) do
            -- use filename instead of bufnr so it can be reloaded
            entry.filename = vim.api.nvim_buf_get_name(entry.bufnr)
            entry.bufnr = nil
          end

          local setqflist = "call setqflist(" .. vim.fn.string(qflist) .. ")"
          local setqfinfo = 'call setqflist([], "a", ' .. vim.fn.string(qfinfo) .. ")"
          return { setqflist, setqfinfo, "copen" }
        end,
      },
    },
  },
}
