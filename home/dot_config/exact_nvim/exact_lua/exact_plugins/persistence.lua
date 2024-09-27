return {
  {
    "folke/persistence.nvim",
    enabled = false,
    event = "BufReadPre", -- this will only start session saving when an actual file was opened
    opts = {
      need = 0,
      branch = false,
    },
  },
  {
    "rmagatti/auto-session",
    lazy = false,

    ---enables autocomplete for opts
    ---@module "auto-session"
    ---@type AutoSession.Config
    opts = {
      suppressed_dirs = { "~/", "~/code", "~/Downloads", "/" },
      -- log_level = 'debug',
    },
  },
}
