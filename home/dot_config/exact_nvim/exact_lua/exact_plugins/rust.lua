return {
  {
    "nvim-treesitter/nvim-treesitter",
    opts = function(_, opts)
      opts.ensure_installed = vim.list_extend(opts.ensure_installed or {}, { "rust", "toml" })
      return opts
    end,
  },
  {
    "mason-org/mason.nvim",
    opts = function(_, opts)
      opts.ensure_installed = vim.list_extend(opts.ensure_installed or {}, { "codelldb", "taplo" })
      return opts
    end,
  },
  {
    "mrcjkb/rustaceanvim",
    version = "^4",
    ft = { "rust" },
    init = function()
      vim.g.rustaceanvim = vim.tbl_deep_extend("force", {
        tools = {
          executor = require("rustaceanvim.executors").termopen,
          hover_actions = {
            auto_focus = true,
          },
        },
        server = {
          default_settings = {
            ["rust-analyzer"] = {
              cargo = {
                allFeatures = true,
              },
              checkOnSave = {
                command = "clippy",
              },
              completion = {
                postfix = {
                  enable = true,
                },
              },
            },
          },
        },
      }, vim.g.rustaceanvim or {})
    end,
  },
  {
    "neovim/nvim-lspconfig",
    opts = {
      servers = {
        rust_analyzer = {},
      },
    },
  },
  {
    "stevearc/conform.nvim",
    opts = function(_, opts)
      opts.formatters_by_ft = vim.tbl_deep_extend("force", opts.formatters_by_ft or {}, {
        rust = { "rustfmt" },
        toml = { "taplo" },
      })
      return opts
    end,
  },
}
