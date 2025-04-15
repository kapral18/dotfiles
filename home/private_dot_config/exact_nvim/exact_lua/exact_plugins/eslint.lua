return {
  {
    "neovim/nvim-lspconfig",
    opts = {
      ---@type lspconfig.options
      servers = {
        eslint = {
          settings = {
            workingDirectories = { mode = "location" },
            codeActionOnSave = {
              mode = "all",
              enable = true,
            },
            format = true,
          },
        },
      },
      setup = {
        eslint = function()
          local formatter = LazyVim.lsp.formatter({
            name = "eslint: lsp",
            primary = false,
            priority = 200,
            filter = "eslint",
          })

          -- register the formatter with LazyVim
          LazyVim.format.register(formatter)
        end,
      },
    },
  },
}
