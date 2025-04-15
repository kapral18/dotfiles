return {
  {
    "neovim/nvim-lspconfig",
    opts = {
      ---@type lspconfig.options
      servers = {
        eslint = {
          settings = {
            workingDirectories = { mode = "auto" },
            codeActionOnSave = {
              mode = "all",
              enable = true,
            },
            format = true,
          },
          root_dir = function()
            return vim.uv.cwd()
          end,
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
