return {
  {
    "mason-org/mason.nvim",
    opts = {
      ensure_installed = { "json-lsp", "prettierd" },
    },
  },
  {
    "neovim/nvim-lspconfig",
    dependencies = {
      "b0o/SchemaStore.nvim",
    },
    opts = function(_, opts)
      opts.servers = opts.servers or {}
      opts.servers.jsonls = vim.tbl_deep_extend("force", {
        settings = {
          json = {
            schemas = require("schemastore").json.schemas(),
            validate = { enable = true },
          },
        },
      }, opts.servers.jsonls or {})
    end,
  },
  {
    "stevearc/conform.nvim",
    opts = function(_, opts)
      opts.formatters_by_ft = opts.formatters_by_ft or {}
      for _, ft in ipairs({ "json", "jsonc" }) do
        opts.formatters_by_ft[ft] = opts.formatters_by_ft[ft] or { "prettierd", "prettier" }
      end
    end,
  },
  {
    "mfussenegger/nvim-lint",
    opts = function(_, opts)
      opts.linters_by_ft = opts.linters_by_ft or {}
      opts.linters_by_ft.json = opts.linters_by_ft.json or { "jsonlint" }
      opts.linters_by_ft.jsonc = opts.linters_by_ft.jsonc or { "jsonlint" }
    end,
  },
}
