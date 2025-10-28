-- local ft_js = { "typescript", "javascript", "typescriptreact", "javascriptreact" }

return {
  {
    "nvim-treesitter/nvim-treesitter",
    opts = {
      ensure_installed = { "html", "css", "scss" },
    },
  },
  {
    "mason-org/mason.nvim",
    opts = {
      ensure_installed = { "html-lsp", "css-variables-language-server", "css-lsp", "htmlhint", "stylelint" },
    },
  },
  {
    "neovim/nvim-lspconfig",
    opts = {
      servers = {
        html = {},
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
        css = { "stylelint", "prettier" },
        scss = { "stylelint", "prettier" },
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
}
