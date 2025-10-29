return {
  {
    "nvim-treesitter/nvim-treesitter",
    opts = function(_, opts)
      opts.ensure_installed = vim.list_extend(opts.ensure_installed or {}, { "yaml" })
      return opts
    end,
  },
  {
    "neovim/nvim-lspconfig",
    dependencies = {
      { "antosha417/nvim-lsp-file-operations", config = true },
    },
    opts = {
      servers = {
        yamlls = {
          settings = {
            yaml = {
              customTags = {
                "!reference sequence",
              },
            },
          },
        },
      },
    },
  },
  {
    "stevearc/conform.nvim",
    opts = function(_, opts)
      opts.formatters_by_ft = vim.tbl_deep_extend("force", opts.formatters_by_ft or {}, {
        yaml = { "prettierd", "prettier", stop_after_first = true },
      })
      return opts
    end,
  },
}
