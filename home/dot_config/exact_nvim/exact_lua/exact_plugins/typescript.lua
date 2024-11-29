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
        ts_ls = {
          enable = false,
        },
        -- @deprecated
        tsserver = {
          enabled = false,
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
        opts = function(_, opts)
          local keys = require("lazyvim.plugins.lsp.keymaps").get()

          -- keys is a table of tables, where each table is a keymap, with 1st position being the key
          -- and the 2nd position being the value
          -- find me the keymap that has the key "<leader>CR"
          local found = nil
          for _, keymap in ipairs(keys) do
            if keymap[1] == "<leader>cR" then
              -- print the value of the keymap
              found = keymap
            end
          end

          local lazyvim_cr_rhs = found and found[2] or 'echo "No keymap found"'

          keys[#keys + 1] = {
            "<leader>cR",
            function()
              if vim.tbl_contains(ft_js, vim.bo.filetype) then
                vim.cmd("TSToolsRenameFile")
              else
                vim.cmd(lazyvim_cr_rhs)
              end
            end,
            desc = "Rename File",
            buffer = true,
          }

          vim.api.nvim_create_autocmd("LspAttach", {
            group = vim.api.nvim_create_augroup("k18.tstools", {}),
            desc = "TSTools Keymaps Override",
            callback = function(ev)
              local client_id = ev.data.client_id

              if not client_id then
                return
              end

              local client = vim.lsp.get_client_by_id(ev.data.client_id)

              if not client then
                return
              end

              if client.name ~= "typescript-tools" then
                return
              end

              -- let eslint/prettier handle formatting
              client.server_capabilities.documentFormattingProvider = false
              client.server_capabilities.documentRangeFormattingProvider = false
            end,
          })

          -- deep merge the opts with the new object
          return vim.tbl_deep_extend("force", opts, {
            -- fixes issues with eslint format error when too nested folders
            -- fixed in neovim v0.11
            -- https://github.com/neovim/neovim/issues/26520#issuecomment-2338591652
            capabilities = {
              workspace = {
                didChangeWatchedFiles = {
                  dynamicRegistration = true,
                },
              },
              textDocument = {
                formatting = { dynamicRegistration = false },
              },
            },
          })
        end,
      },
    },
    ft = ft_js,
    opts = {
      settings = {
        code_lens = "off",
        complete_function_calls = true,
        include_completions_with_insert_text = true,
        separate_diagnostic_server = true,
        publish_diagnostic_on = "insert_leave",
        tsserver_path = nil,
        tsserver_max_memory = 20000,
        tsserver_format_options = {},
        tsserver_file_preferences = {
          completions = { completeFunctionCalls = true },
          init_options = { preferences = { disableSuggestions = true } },
          importModuleSpecifierPreference = "project-relative",
          jsxAttributeCompletionStyle = "braces",
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

      for _, language in ipairs({ "typescript", "javascript", "typescriptreact", "javascriptreact", "tsx", "jsx" }) do
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
  {
    "echasnovski/mini.icons",
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
}
