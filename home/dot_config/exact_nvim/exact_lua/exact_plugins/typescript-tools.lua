local util = require("util")

local ft_js = {
  "tsx",
  "jsx",
  "javascript",
  "javascriptreact",
  "javascript.jsx",
  "typescript",
  "typescriptreact",
  "typescript.tsx",
}

return {
  {
    "nvim-treesitter/nvim-treesitter",
    opts = function(_, opts)
      opts.ensure_installed = vim.list_extend(opts.ensure_installed or {}, { "typescript", "tsx", "javascript", "jsdoc" })
      return opts
    end,
  },
  {
    "mason-org/mason.nvim",
    opts = function(_, opts)
      opts.ensure_installed = vim.list_extend(opts.ensure_installed or {}, { "prettierd", "prettier" })
      return opts
    end,
  },
  {
    "pmizio/typescript-tools.nvim",
    lazy = false,
    keys = {
      {
        "gR",
        "<cmd>TSToolsFileReferences<cr>",
        ft = ft_js,
        desc = "TSTools: File References",
        buffer = true,
      },
    },
    dependencies = {
      "nvim-lua/plenary.nvim",
      {
        "neovim/nvim-lspconfig",
        dependencies = {
          { "b0o/SchemaStore.nvim" },
        },
        opts = {
          servers = {
            ts_ls = {
              enabled = false,
            },
            -- @deprecated
            tsserver = {
              enabled = false,
            },
            ["*"] = {
              keys = {
                {
                  "<leader>cR",
                  function()
                    if vim.tbl_contains(ft_js, vim.bo.filetype) then
                      vim.cmd("TSToolsRenameFile")
                    else
                      vim.lsp.buf.rename()
                    end
                  end,
                  desc = "Rename File",
                  has = "rename",
                },
              },
            },
          },
          setup = {
            tsserver = function()
              -- disable tsserver
              return true
            end,
            ts_ls = function()
              -- disable ts_ls
              return true
            end,
          },
        },
      },
    },
    ft = ft_js,
    opts = {
      settings = {
        code_lens = "off",
        complete_function_calls = false,
        include_completions_with_insert_text = true,
        separate_diagnostic_server = true,
        publish_diagnostic_on = "insert_leave",
        tsserver_path = nil,
        tsserver_max_memory = 32000,
        tsserver_format_options = {
          allowIncompleteCompletions = false,
        },
        tsserver_file_preferences = {
          completions = { completeFunctionCalls = false },
          includeInlayParameterNameHints = "none",
          includeCompletionsForModuleExports = true,
          init_options = {
            preferences = {
              disableSuggestions = true,
            },
          },
          importModuleSpecifierPreference = "project-relative",
          jsxAttributeCompletionStyle = "braces",
        },
        tsserver_locale = "en",
        disable_member_code_lens = true,
        jsx_close_tag = { enable = false },
      },
      root_dir = function()
        return util.get_project_root()
      end,
    },
  },
  {
    "dmmulroy/tsc.nvim",
    opts = {
      auto_start_watch_mode = false,
      use_trouble_qflist = false,
      flags = {
        watch = false,
      },
    },
    keys = {
      { "<leader>cttc", ft = { "typescript", "typescriptreact" }, "<cmd>TSC<cr>",     desc = "Type Check" },
      { "<leader>cttq", ft = { "typescript", "typescriptreact" }, "<cmd>TSCOpen<cr>", desc = "Type Check Quickfix" },
    },
    ft = {
      "typescript",
      "typescriptreact",
    },
    cmd = {
      "TSC",
      "TSCOpen",
      "TSCClose",
    },
  },
  {
    "nvim-mini/mini.icons",
    opts = {
      file = {
        [".eslintrc.js"] = { glyph = "󰱺", hl = "MiniIconsYellow" },
        [".node-version"] = { glyph = "", hl = "MiniIconsGreen" },
        [".prettierrc"] = { glyph = "", hl = "MiniIconsPurple" },
        [".yarnrc.yml"] = { glyph = "", hl = "MiniIconsBlue" },
        ["eslint.config.js"] = { glyph = "󰱺", hl = "MiniIconsYellow" },
        ["package.json"] = { glyph = "", hl = "MiniIconsGreen" },
        ["tsconfig.json"] = { glyph = "", hl = "MiniIconsAzure" },
        ["tsconfig.build.json"] = { glyph = "", hl = "MiniIconsAzure" },
        ["yarn.lock"] = { glyph = "", hl = "MiniIconsBlue" },
      },
    },
  },
  {
    "stevearc/conform.nvim",
    opts = function(_, opts)
      opts.formatters_by_ft = vim.tbl_deep_extend("force", opts.formatters_by_ft or {}, {
        javascript = { "prettierd", "prettier", stop_after_first = true },
        javascriptreact = { "prettierd", "prettier", stop_after_first = true },
        typescript = { "prettierd", "prettier", stop_after_first = true },
        typescriptreact = { "prettierd", "prettier", stop_after_first = true },
      })
      return opts
    end,
  },
}
