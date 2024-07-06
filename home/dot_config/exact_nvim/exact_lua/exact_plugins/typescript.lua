local ft_js = {
  "javascript",
  "javascriptreact",
  "javascript.jsx",
  "typescript",
  "typescriptreact",
  "typescript.tsx",
}
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
        tsserver = {
          enabled = false,
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
      setup = {
        tsserver = function()
          -- disable tsserver
          return false
        end,
      },
    },
  },
  {
    "Redoxahmii/json-to-ts.nvim",
    build = "sh install.sh yarn",
    ft = ft_json,
    keys = {
      {
        "<leader>cjt",
        "<CMD>ConvertJSONtoTS<CR>",
        desc = "Convert JSON to TS",
        ft = ft_json,
      },
      {
        "<leader>cjb",
        "<CMD>ConvertJSONtoTSBuffer<CR>",
        desc = "Convert JSON to TS in buffer",
        ft = ft_json,
      },
    },
  },
  {
    "pmizio/typescript-tools.nvim",
    event = "BufReadPre",
    dependencies = { "nvim-lua/plenary.nvim", "neovim/nvim-lspconfig", "artemave/workspace-diagnostics.nvim" },
    keys = {
      { "gD", ft = ft_js, "<cmd>TSToolsGoToSourceDefinition<cr>", desc = "TSTools: Goto Source Definition" },
      { "gR", ft = ft_js, "<cmd>TSToolsFileReferences<cr>", desc = "TSTools: File References" },
      { "<leader>cia", ft = ft_js, "<cmd>TSToolsAddMissingImports<cr>", desc = "TSTools: Add missing imports" },
      { "<leader>cir", ft = ft_js, "<cmd>TSToolsRemoveUnusedImports<cr>", desc = "TSTools: Remove Unused Imports" },
      { "<leader>cD", ft = ft_js, "<cmd>TSToolsFixAll<cr>", desc = "TSTools: Fix all diagnostics" },
      { "<leader>cR", ft = ft_js, "<cmd>TsToolsRenameFile<cr>", desc = "TSTools: Rename File" },
    },
    opts = {
      settings = {
        code_lens = "off",
        complete_function_calls = true,
        include_completions_with_insert_text = true,
        separate_diagnostic_server = true,
        publish_diagnostic_on = "insert_leave",
        tsserver_path = nil,
        tsserver_plugins = {},
        tsserver_max_memory = 32500,
        tsserver_format_options = {},
        tsserver_file_preferences = {
          completions = { completeFunctionCalls = true },
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
      use_trouble_qflist = false,
      flags = {
        watch = false,
      },
    },
    keys = {
      { "<leader>cttc", ft = { "typescript", "typescriptreact" }, "<cmd>TSC<cr>", desc = "Type Check" },
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
