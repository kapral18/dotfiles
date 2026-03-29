local fs_util = require("util.fs")
local web_toolchain = require("util.web_toolchain")

return {
  {
    "nvim-treesitter/nvim-treesitter",
    opts = function(_, opts)
      opts.ensure_installed =
        vim.list_extend(opts.ensure_installed or {}, { "typescript", "tsx", "javascript", "jsx", "jsdoc" })
      return opts
    end,
  },
  {
    "mason-org/mason.nvim",
    opts = function(_, opts)
      opts.ensure_installed =
        vim.list_extend(opts.ensure_installed or {}, { "biome", "oxfmt", "oxlint", "prettierd", "prettier" })
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
        on_attach = function(client)
          client.server_capabilities.documentFormattingProvider = false
          client.server_capabilities.documentRangeFormattingProvider = false
        end,
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
        javascript = web_toolchain.web_formatters,
        javascriptreact = web_toolchain.web_formatters,
        typescript = web_toolchain.web_formatters,
        typescriptreact = web_toolchain.web_formatters,
        vue = web_toolchain.web_formatters,
        svelte = web_toolchain.web_formatters,
        astro = web_toolchain.web_formatters,
      })
      return opts
    end,
  },
  {
    "mfussenegger/nvim-lint",
    optional = true,
    opts = function(_, opts)
      opts.linters_by_ft = vim.tbl_deep_extend("force", opts.linters_by_ft or {}, {
        javascript = { "oxlint" },
        javascriptreact = { "oxlint" },
        typescript = { "oxlint" },
        typescriptreact = { "oxlint" },
        vue = { "oxlint" },
        svelte = { "oxlint" },
        astro = { "oxlint" },
      })

      -- Only enable oxlint when a repo explicitly opts into it.
      -- (nvim-lint will call this with { filename, dirname }).
      opts.linters = opts.linters or {}
      opts.linters.oxlint = vim.tbl_deep_extend("force", opts.linters.oxlint or {}, {
        condition = function(ctx)
          if not ctx or type(ctx.dirname) ~= "string" or ctx.dirname == "" then
            return false
          end
          local found = vim.fs.find({ ".oxlintrc.json", ".oxlintrc.jsonc", "oxlint.config.ts" }, {
            path = ctx.dirname,
            upward = true,
          })[1]
          return found ~= nil
        end,
      })

      return opts
    end,
  },
}
