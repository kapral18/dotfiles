local fs_util = require("util.fs")

return {
  {
    "nvim-treesitter/nvim-treesitter",
    opts = function(_, opts)
      opts.ensure_installed =
        vim.list_extend(opts.ensure_installed or {}, { "typescript", "tsx", "javascript", "jsdoc" })
      return opts
    end,
  },
  {
    "mason-org/mason.nvim",
    opts = function(_, opts)
      opts.ensure_installed = vim.list_extend(opts.ensure_installed or {}, { "prettierd", "prettier" })
      return opts
    end,
  },
  {
    "neovim/nvim-lspconfig",
    dependencies = {
      { "b0o/SchemaStore.nvim" },
    },
    opts = function(_, opts)
      opts.servers = opts.servers or {}

      opts.servers.tsgo = {
        root_dir = function(bufnr, on_dir)
          on_dir(fs_util.get_project_root())
        end,
        settings = {
          typescript = {
            inlayHints = {
              parameterNames = { enabled = "none" },
              parameterTypes = { enabled = false },
              variableTypes = { enabled = false },
              propertyDeclarationTypes = { enabled = false },
              functionLikeReturnTypes = { enabled = false },
              enumMemberValues = { enabled = false },
            },
          },
        },
      }

      return opts
    end,
  },
  {
    "dmmulroy/tsc.nvim",
    opts = {
      auto_start_watch_mode = false,
      use_trouble_qflist = false,
      flags = {
        watch = false,
      },
    },
    keys = {
      { "<leader>cttc", ft = { "typescript", "typescriptreact" }, "<cmd>TSC<cr>", desc = "Type Check" },
      { "<leader>cttq", ft = { "typescript", "typescriptreact" }, "<cmd>TSCOpen<cr>", desc = "Type Check Quickfix" },
    },
    ft = {
      "typescript",
      "typescriptreact",
    },
    cmd = {
      "TSC",
      "TSCOpen",
      "TSCClose",
    },
  },
  {
    "nvim-mini/mini.icons",
    opts = {
      file = {
        [".eslintrc.js"] = { glyph = "󰱺", hl = "MiniIconsYellow" },
        [".node-version"] = { glyph = "", hl = "MiniIconsGreen" },
        [".prettierrc"] = { glyph = "", hl = "MiniIconsPurple" },
        [".yarnrc.yml"] = { glyph = "", hl = "MiniIconsBlue" },
        ["eslint.config.js"] = { glyph = "󰱺", hl = "MiniIconsYellow" },
        ["package.json"] = { glyph = "", hl = "MiniIconsGreen" },
        ["tsconfig.json"] = { glyph = "", hl = "MiniIconsAzure" },
        ["tsconfig.build.json"] = { glyph = "", hl = "MiniIconsAzure" },
        ["yarn.lock"] = { glyph = "", hl = "MiniIconsBlue" },
      },
    },
  },
  {
    "stevearc/conform.nvim",
    opts = function(_, opts)
      opts.formatters_by_ft = vim.tbl_deep_extend("force", opts.formatters_by_ft or {}, {
        javascript = { "prettierd", "prettier", stop_after_first = true },
        javascriptreact = { "prettierd", "prettier", stop_after_first = true },
        typescript = { "prettierd", "prettier", stop_after_first = true },
        typescriptreact = { "prettierd", "prettier", stop_after_first = true },
      })
      return opts
    end,
  },
}
