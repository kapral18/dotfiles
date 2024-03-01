return {
  "neovim/nvim-lspconfig",
  dependencies = {
    { "antosha417/nvim-lsp-file-operations", config = true },
  },
  opts = {
    inlay_hints = {
      enabled = false,
    },
    servers = {
      lua_ls = {
        settings = {
          Lua = {
            hint = {
              enable = true,
              setType = true,
            },
          },
        },
      },
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
}
