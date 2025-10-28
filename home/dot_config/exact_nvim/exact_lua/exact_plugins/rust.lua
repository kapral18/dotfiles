return {
  {
    "nvim-treesitter/nvim-treesitter",
    opts = {
      ensure_installed = { "rust", "toml" },
    },
  },
  {
    "mason-org/mason.nvim",
    opts = {
      ensure_installed = { "rust-analyzer", "codelldb", "taplo" },
    },
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
    opts = function(_, opts)
      opts.servers = opts.servers or {}
      opts.servers.rust_analyzer = vim.tbl_deep_extend("force", {}, opts.servers.rust_analyzer or {})
    end,
  },
  {
    "stevearc/conform.nvim",
    opts = function(_, opts)
      opts.formatters_by_ft = opts.formatters_by_ft or {}
      opts.formatters_by_ft.toml = opts.formatters_by_ft.toml or {}
      if not vim.tbl_contains(opts.formatters_by_ft.toml, "taplo") then
        table.insert(opts.formatters_by_ft.toml, "taplo")
      end

      opts.formatters_by_ft.rust = opts.formatters_by_ft.rust or {}
      if not vim.tbl_contains(opts.formatters_by_ft.rust, "rustfmt") then
        table.insert(opts.formatters_by_ft.rust, "rustfmt")
      end
      return opts
    end,
  },
}
