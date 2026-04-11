return {
  {
    "rmagatti/auto-session",
    -- Must be available before VimEnter so auto-restore hooks can run.
    lazy = false,
    dependencies = {
      { "nvim-telescope/telescope.nvim", opt = true },
    },
    cmd = {
      "AutoSession",
      "Autosession",
    },
    keys = {
      { "<localleader>ss", "<cmd>AutoSession save<CR>", desc = "Save session" },
    },
    ---enables autocomplete for opts
    ---@module "auto-session"
    ---@type AutoSession.Config
    opts = {
      suppressed_dirs = { "~/", "~/code", "~/Downloads", "/" },
      use_git_branch = true,
      session_lens = { load_on_setup = false },
      bypass_save_filetypes = { "packdashboard", "packtrace" },
      close_filetypes_on_save = { "checkhealth", "packdashboard", "packtrace" },
      -- Suppress chezmoi.vim filetype detection during restore to prevent
      -- keep_filetype → FileType → keep_filetype infinite recursion (E218).
      -- chezmoi_keepfiletype autocmds normally get cleaned up by VimEnter/
      -- BufWinEnter, but those don't fire for buffers opened inside VimEnter.
      pre_restore_cmds = {
        function()
          vim.g["chezmoi#detect_ignore_pattern"] = ".*"
        end,
      },
      -- `localoptions` is excluded from `sessionoptions` to prevent stale
      -- window/buffer options (wrap, spell, etc.) from overriding autocmds.
      -- Without it the session file omits `setlocal filetype=…`, so we re-run
      -- filetype detection for any restored buffer that lost its filetype.
      post_restore_cmds = {
        function()
          vim.g["chezmoi#detect_ignore_pattern"] = nil
          vim.schedule(function()
            for _, buf in ipairs(vim.api.nvim_list_bufs()) do
              if vim.api.nvim_buf_is_valid(buf) and vim.bo[buf].buflisted then
                local name = vim.api.nvim_buf_get_name(buf)
                if name ~= "" then
                  vim.api.nvim_buf_call(buf, function()
                    vim.cmd("filetype detect")
                  end)
                end
              end
            end
          end)
        end,
      },
    },
  },
}
