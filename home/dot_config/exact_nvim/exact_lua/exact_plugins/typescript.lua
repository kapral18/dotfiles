local ft_js = { "typescript", "typescriptreact", "javascript", "javascriptreact" }
local ft_json = { "json", "jsonl", "jsonc" }
local util = require("lspconfig.util")

return {
  {
    "nvim-treesitter/nvim-treesitter",
    opts = function(_, opts)
      vim.list_extend(opts.ensure_installed, {
        "typescript",
        "tsx",
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
    ft = ft_json,
    keys = {
      {
        "<leader>cu",
        "<CMD>ConvertJSONtoTS<CR>",
        desc = "Convert JSON to TS",
        ft = ft_json,
      },
      {
        "<leader>ct",
        "<CMD>ConvertJSONtoTSBuffer<CR>",
        desc = "Convert JSON to TS in buffer",
        ft = ft_json,
      },
    },
  },
  {
    "pmizio/typescript-tools.nvim",
    event = "BufReadPre",
    dependencies = { "nvim-lua/plenary.nvim", "neovim/nvim-lspconfig" },
    keys = {
      { "<leader>cO", ft = ft_js, "<cmd>TSToolsOrganizeImports<cr>", desc = "Organize Imports" },
      { "<leader>cR", ft = ft_js, "<cmd>TSToolsRemoveUnusedImports<cr>", desc = "Remove Unused Imports" },
      { "<leader>cM", ft = ft_js, "<cmd>TSToolsAddMissingImports<cr>", desc = "Add Missing Imports" },
    },
    opts = {
      on_attach = function(client, bufnr)
        if client.server_capabilities then
          client.server_capabilities.documentFormattingProvider = false
          client.server_capabilities.documentRangeFormattingProvider = false
          client.server_capabilities.semanticTokensProvider = nil
          -- vim.api.nvim_set_hl(0, "@lsp.mod.readonly.typescriptreact", { link = "@variable" })
          -- vim.api.nvim_set_hl(0, "@lsp.typemod.variable.declaration.typescriptreact", { link = "@variable" })
          -- vim.api.nvim_set_hl(0, "@variable.member.tsx", { link = "@property" })
        end
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
  {
    "dmmulroy/tsc.nvim",
    opts = {
      auto_start_watch_mode = false,
      use_trouble_qflist = true,
      flags = {
        watch = false,
      },
    },
    keys = {
      { "<leader>ct", ft = { "typescript", "typescriptreact" }, "<cmd>TSC<cr>", desc = "Type Check" },
      { "<leader>xy", ft = { "typescript", "typescriptreact" }, "<cmd>TSCOpen<cr>", desc = "Type Check Quickfix" },
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
    "mfussenegger/nvim-dap",
    optional = true,
    dependencies = {
      {
        "williamboman/mason.nvim",
        opts = function(_, opts)
          opts.ensure_installed = opts.ensure_installed or {}
          table.insert(opts.ensure_installed, "js-debug-adapter")
        end,
      },
    },
    opts = function()
      local dap = require("dap")
      if not dap.adapters["pwa-node"] then
        require("dap").adapters["pwa-node"] = {
          type = "server",
          host = "localhost",
          port = "${port}",
          executable = {
            command = "node",
            -- 💀 Make sure to update this path to point to your installation
            args = {
              require("mason-registry").get_package("js-debug-adapter"):get_install_path()
                .. "/js-debug/src/dapDebugServer.js",
              "${port}",
            },
          },
        }
      end
      if not dap.adapters["node"] then
        dap.adapters["node"] = function(cb, config)
          if config.type == "node" then
            config.type = "pwa-node"
          end
          local nativeAdapter = dap.adapters["pwa-node"]
          if type(nativeAdapter) == "function" then
            nativeAdapter(cb, config)
          else
            cb(nativeAdapter)
          end
        end
      end

      for _, language in ipairs({ "typescript", "javascript", "typescriptreact", "javascriptreact" }) do
        if not dap.configurations[language] then
          dap.configurations[language] = {
            {
              type = "pwa-node",
              request = "launch",
              name = "Launch file",
              program = "${file}",
              cwd = "${workspaceFolder}",
            },
            {
              type = "pwa-node",
              request = "attach",
              name = "Attach",
              processId = require("dap.utils").pick_process,
              cwd = "${workspaceFolder}",
            },
          }
        end
      end
    end,
  },
}
