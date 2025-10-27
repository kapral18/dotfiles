local util = require("util")

return {
  {
    "neovim/nvim-lspconfig",
    opts = {
      ---@type table<string, vim.lsp.Config>
      servers = {
        eslint = {
          settings = {
            -- temporary until https://github.com/microsoft/vscode-eslint/pull/2076 is merged
            workingDirectory = { mode = "location" },
            codeActionOnSave = {
              mode = "all",
            },
            format = true,
          },
        },
      },
      setup = {
        eslint = function()
          local formatter = util.lsp.formatter({
            name = "eslint: lsp",
            primary = false,
            priority = 200,
            filter = "eslint",
          })

          util.format.register(formatter)
        end,
      },
    },
  },
}
