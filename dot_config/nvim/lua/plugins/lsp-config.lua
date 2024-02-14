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
      tsserver = {
        init_options = {
          preferences = {
            disableSuggestions = true,
          },
        },
        settings = {
          typescript = {
            format = {
              indentSize = vim.o.shiftwidth,
              convertTabsToSpaces = vim.o.expandtab,
              tabSize = vim.o.tabstop,
            },
            inlayHints = {
              includeInlayParameterNameHints = "all",
              includeInlayParameterNameHintsWhenArgumentMatchesName = true,
              includeInlayFunctionParameterTypeHints = true,
              includeInlayVariableTypeHints = true,
              includeInlayVariableTypeHintsWhenTypeMatchesName = true,
              includeInlayPropertyDeclarationTypeHints = true,
              includeInlayFunctionLikeReturnTypeHints = true,
              includeInlayEnumMemberValueHints = true,
            },
          },
          javascript = {
            format = {
              indentSize = vim.o.shiftwidth,
              convertTabsToSpaces = vim.o.expandtab,
              tabSize = vim.o.tabstop,
            },
            inlayHints = {
              includeInlayParameterNameHints = "all",
              includeInlayParameterNameHintsWhenArgumentMatchesName = true,
              includeInlayFunctionParameterTypeHints = true,
              includeInlayVariableTypeHints = true,
              includeInlayVariableTypeHintsWhenTypeMatchesName = true,
              includeInlayPropertyDeclarationTypeHints = true,
              includeInlayFunctionLikeReturnTypeHints = true,
              includeInlayEnumMemberValueHints = true,
            },
          },
          completions = {
            completeFunctionCalls = true,
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
