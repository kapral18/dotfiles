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
      -- Prevent transient dashboards/debug popups from polluting saved sessions.
      bypass_save_filetypes = { "packdashboard", "packtrace" },
      close_filetypes_on_save = { "checkhealth", "packdashboard", "packtrace" },
      -- `localoptions` is excluded from `sessionoptions` to prevent stale
      -- window/buffer options (wrap, spell, etc.) from overriding autocmds.
      -- Without it the session file omits `setlocal filetype=…`, so we re-run
      -- filetype detection for any restored buffer that lost its filetype.
      post_restore_cmds = {
        function()
          vim.schedule(function()
            for _, buf in ipairs(vim.api.nvim_list_bufs()) do
              if vim.api.nvim_buf_is_valid(buf) and vim.bo[buf].buflisted and vim.bo[buf].filetype == "" then
                if vim.api.nvim_buf_get_name(buf) ~= "" then
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
