local ft = { "typescript", "typescriptreact", "javascript", "javascriptreact" }

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
        tsserver = {},
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
  },
  {
    "pmizio/typescript-tools.nvim",
    event = "BufReadPre",
    dependencies = { "nvim-lua/plenary.nvim", "neovim/nvim-lspconfig" },
    keys = {
      { "<leader>cO", ft = ft, "<cmd>TSToolsOrganizeImports<cr>", desc = "Organize Imports" },
      { "<leader>cR", ft = ft, "<cmd>TSToolsRemoveUnusedImports<cr>", desc = "Remove Unused Imports" },
      { "<leader>cM", ft = ft, "<cmd>TSToolsAddMissingImports<cr>", desc = "Add Missing Imports" },
    },
    opts = {
      cmd = { "typescript-language-server", "--stdio" },
      on_attach = function(client, bufnr)
        client.server_capabilities.documentFormattingProvider = true
        client.server_capabilities.documentRangeFormattingProvider = true
        -- vim.api.nvim_set_hl(0, "@lsp.mod.readonly.typescriptreact", { link = "@variable" })
        -- vim.api.nvim_set_hl(0, "@lsp.typemod.variable.declaration.typescriptreact", { link = "@variable" })
        -- vim.api.nvim_set_hl(0, "@variable.member.tsx", { link = "@property" })
      end,
      settings = {
        code_lens = "all",
        expose_as_code_action = "all",
        complete_function_calls = true,
        include_completions_with_insert_text = true,
        tsserver_file_preferences = {
          completions = { completeFunctionCalls = true },
          init_options = { preferences = { disableSuggestions = true } },
          includeCompletionsForModuleExports = true,
          quotePreference = "auto",
        },
      },
    },
  },
}
