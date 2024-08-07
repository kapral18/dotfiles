-- local ft_js = { "typescript", "javascript", "typescriptreact", "javascriptreact" }

return {
  {
    "nvim-treesitter/nvim-treesitter",
    opts = function(_, opts)
      -- add tsx and treesitter
      vim.list_extend(opts.ensure_installed, {
        "html",
        "css",
        "scss",
      })
    end,
  },
  {
    "williamboman/mason.nvim",
    opts = function(_, opts)
      vim.list_extend(opts.ensure_installed, {
        "emmet-language-server",
        "html-lsp",
        "cssmodules-language-server",
        "css-variables-language-server",
        "css-lsp",
        "htmlhint",
        "stylelint",
      })
    end,
  },
  {
    "neovim/nvim-lspconfig",
    opts = {
      servers = {
        -- tailwindcss = {},
        emmet_language_server = {},
        html = {},
        cssmodules_ls = {},
        css_variables = {},
        cssls = {
          lint = {
            compatibleVendorPrefixes = "ignore",
            vendorPrefix = "ignore",
            unknownVendorSpecificProperties = "ignore",

            -- unknownProperties = "ignore", -- duplicate with stylelint

            duplicateProperties = "warning",
            emptyRules = "warning",
            importStatement = "warning",
            zeroUnits = "warning",
            fontFaceProperties = "warning",
            hexColorLength = "warning",
            argumentsInColorFunction = "warning",
            unknownAtRules = "warning",
            ieHack = "warning",
            propertyIgnoredDueToDisplay = "warning",
          },
        },
      },
      setup = {},
    },
  },
  {
    "stevearc/conform.nvim",
    opts = {
      formatters_by_ft = {
        css = { "stylelint", { "prettier" } },
        scss = { "stylelint", { "prettier" } },
      },
    },
  },
  {
    "mfussenegger/nvim-lint",
    opts = {
      linters_by_ft = {
        ["html"] = { "htmlhint" },
        ["css"] = { "stylelint" },
        ["scss"] = { "stylelint" },
        ["less"] = { "stylelint" },
        ["sugarss"] = { "stylelint" },
        ["vue"] = { "stylelint" },
        ["wxss"] = { "stylelint" },
      },
    },
  },
  {
    "NvChad/nvim-colorizer.lua",
    opts = {
      user_default_options = {
        -- tailwind = true,
      },
    },
  },
  -- {
  --   "hrsh7th/nvim-cmp",
  --   dependencies = {
  --     { "roobert/tailwindcss-colorizer-cmp.nvim", config = true },
  --   },
  --   opts = function(_, opts)
  --     local format_kinds = opts.formatting.format
  --
  --     opts.formatting.format = function(entry, item)
  --       format_kinds(entry, item)
  --       return require("tailwindcss-colorizer-cmp").formatter(entry, item)
  --     end
  --   end,
  -- },
  -- {
  --   "MaximilianLloyd/tw-values.nvim",
  --   ft = ft_js,
  --   keys = {
  --     {
  --       "<leader>cT",
  --       "<cmd>TWValues<cr>",
  --       desc = "Tailwind CSS values",
  --       ft = ft_js,
  --     },
  --   },
  --   opts = {},
  -- },
}
