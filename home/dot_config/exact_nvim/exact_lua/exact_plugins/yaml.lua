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
  {
    "someone-stole-my-name/yaml-companion.nvim",
    ft = { "yaml" },
    dependencies = {
      { "neovim/nvim-lspconfig" },
      { "nvim-lua/plenary.nvim" },
      { "nvim-telescope/telescope.nvim" },
    },
    opts = {
      lspconfig = {
        capabilities = {
          textDocument = {
            foldingRange = {
              dynamicRegistration = false,
              lineFoldingOnly = true,
            },
          },
        },
      },
    },
    config = function(_, opts)
      local cfg = require("yaml-companion").setup(opts)
      require("lspconfig")["yamlls"].setup(cfg)
      LazyVim.on_load("telescope.nvim", function()
        require("telescope").load_extension("yaml_schema")
      end)
    end,
    keys = {
      { "<leader>cy", "<cmd>Telescope yaml_schema<cr>", desc = "YAML Schema" },
    },
  },
}
