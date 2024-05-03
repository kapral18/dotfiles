local ft = { "typescript", "typescriptreact", "javascript", "javascriptreact" }
local util = require("lspconfig.util")

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
        tsserver = {
          on_init = function(client)
            client.server_capabilities.documentFormattingProvider = false
            client.server_capabilities.documentFormattingRangeProvider = false
            client.server_capabilities.semanticTokensProvider = nil
          end,
        },
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
        client.server_capabilities.documentFormattingProvider = false
        client.server_capabilities.documentRangeFormattingProvider = false
        client.server_capabilities.semanticTokensProvider = nil
        -- vim.api.nvim_set_hl(0, "@lsp.mod.readonly.typescriptreact", { link = "@variable" })
        -- vim.api.nvim_set_hl(0, "@lsp.typemod.variable.declaration.typescriptreact", { link = "@variable" })
        -- vim.api.nvim_set_hl(0, "@variable.member.tsx", { link = "@property" })
      end,
      settings = {
        code_lens = "off",
        expose_as_code_action = "all",
        complete_function_calls = false,
        include_completions_with_insert_text = true,
        separate_diagnostic_server = true,
        publish_diagnostic_on = "insert_leave",
        tsserver_path = nil,
        tsserver_plugins = {},
        tsserver_max_memory = 16250,
        tsserver_format_options = {},
        tsserver_file_preferences = {
          completions = { completeFunctionCalls = false },
          init_options = { preferences = { disableSuggestions = true } },
          includeCompletionsForModuleExports = true,
          quotePreference = "auto",
        },
        tsserver_locale = "en",
        disable_member_code_lens = true,
      },
      root_dir = util.root_pattern(".git", "yarn.lock", "package-lock.json"),
    },
  },
}
