return {
  {
    "nvim-treesitter/nvim-treesitter",
    opts = function(_, opts)
      opts.ensure_installed = vim.list_extend(opts.ensure_installed or {}, { "fish" })
      return opts
    end,
  },
  {
    "neovim/nvim-lspconfig",
    opts = {
      servers = {
        fish_lsp = {},
      },
    },
  },
  {
    "stevearc/conform.nvim",
    opts = function(_, opts)
      opts.formatters_by_ft = vim.tbl_deep_extend("force", opts.formatters_by_ft or {}, {
        fish = { "fish_indent" },
      })
      return opts
    end,
  },
  {
    "mfussenegger/nvim-lint",
    opts = function(_, opts)
      opts.linters_by_ft = vim.tbl_deep_extend("force", opts.linters_by_ft or {}, {
        fish = { "fish" },
      })
      return opts
    end,
  },
}
