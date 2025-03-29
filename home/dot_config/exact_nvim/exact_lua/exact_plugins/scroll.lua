return {
  {
    "lewis6991/satellite.nvim",
    opts = {
      winblend = 0,
      excluded_filetypes = {
        "NvimTree",
        "TelescopePrompt",
        "alpha",
        "commit",
        "dap-repl",
        "dapui_breakpoints",
        "dapui_console",
        "dapui_scopes",
        "dapui_stacks",
        "dapui_watches",
        "dashboard",
        "fugitive",
        "fugitiveblame",
        "fzf",
        "git",
        "gitcommit",
        "grug-far",
        "lir",
        "neo-tree",
        "noice",
        "packer",
        "prompt",
        "startify",
        "telescope",
      },
      current_only = true,
      diagnostic = {
        min_severity = vim.diagnostic.severity.ERROR,
      },
      search = {
        enable = false,
      },
      gitsigns = {
        enable = false,
      },
      marks = {
        enable = false,
      },
    },
  },
}
