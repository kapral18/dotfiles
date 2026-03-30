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
    },
  },
}
