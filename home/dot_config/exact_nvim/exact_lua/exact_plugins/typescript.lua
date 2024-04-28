return {
  {
    "nvim-treesitter/nvim-treesitter",
    opts = function(_, opts)
      vim.list_extend(opts.ensure_installed, {
        "javascript",
        "jsdoc",
      })
    end,
  },
  {
    "neovim/nvim-lspconfig",
    dependencies = {
      { "b0o/SchemaStore.nvim" },
    },
    opts = {
      servers = {
        jsonls = {
          settings = {
            json = {
              schema = require("schemastore").json.schemas(),
              validate = { enable = true },
            },
          },
        },
      },
    },
  },
  {
    "Redoxahmii/json-to-ts.nvim",
    build = "sh install.sh yarn",
    keys = {
      {
        "<leader>cu",
        "<CMD>ConvertJSONtoTS<CR>",
        desc = "Convert JSON to TS",
      },
      {
        "<leader>ct",
        "<CMD>ConvertJSONtoTSBuffer<CR>",
        desc = "Convert JSON to TS in buffer",
      },
    },
    {
      "pmizio/typescript-tools.nvim",
      event = "BufReadPre",
      dependencies = { "nvim-lua/plenary.nvim", "neovim/nvim-lspconfig" },
      opts = {
        settings = {
          expose_as_code_action = "all",
          complete_function_calls = true,
          include_completions_with_insert_text = true,
          tsserver_file_preferences = {
            includeCompletionsForModuleExports = true,
            quotePreference = "auto",
          },
        },
      },
    },
  },
}
