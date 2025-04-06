return {
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
}
