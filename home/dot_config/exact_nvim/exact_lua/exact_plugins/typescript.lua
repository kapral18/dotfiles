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
    dependencies = {
      "nvim-lua/plenary.nvim",
      {
        "neovim/nvim-lspconfig",
        opts = function()
          local Keys = require("lazyvim.plugins.lsp.keymaps").get()
          local originalKeysCache = {}
          -- stylua: ignore start
          local TSToolsKeys = {
            { key = "gR", ft = ft_js, cmd = "<cmd>TSToolsFileReferences<cr>", desc = "TSTools: File References" },
            { key = "<leader>cia", ft = ft_js, cmd = "<cmd>TSToolsAddMissingImports<cr>", desc = "TSTools: Add missing imports" },
            { key = "<leader>cir", ft = ft_js, cmd = "<cmd>TSToolsRemoveUnusedImports<cr>", desc = "TSTools: Remove Unused Imports",  },
            { key = "<leader>cD", ft = ft_js, cmd = "<cmd>TSToolsFixAll<cr>", desc = "TSTools: Fix all diagnostics" },
            { key = "<leader>cR", ft = ft_js, cmd = "<cmd>TSToolsRenameFile<cr>", desc = "TSTools: Rename File" },
          }
          -- stylua: ignore end

          -- Cache the original keys
          for _, key in ipairs(Keys) do
            local lhs = key[1]
            originalKeysCache[lhs] = { table.unpack(key, 2) }
          end

          vim.api.nvim_create_autocmd("LspAttach", {
            group = vim.api.nvim_create_augroup("k18.tstools", {}),
            desc = "TSTools Keymaps Override",
            callback = function(ev)
              -- if the filetype is typescript or javascript
              if vim.tbl_contains(ft_js, vim.bo[ev.buf].filetype) then
                for cache_lhs, _ in pairs(originalKeysCache) do
                  for _, tstools_keymap in ipairs(TSToolsKeys) do
                    if cache_lhs == tstools_keymap.key then
                      -- remove the original keymaps for the respective LSP keymaps
                      Keys[#Keys + 1] = { cache_lhs, false }
                      -- and add buffer local TSTools keymaps
                      vim.keymap.set(
                        "n",
                        tstools_keymap.key,
                        tstools_keymap.cmd,
                        { desc = tstools_keymap.desc, buffer = true }
                      )
                    end
                  end
                end
              else
                -- If the filetype is not typescript or javascript
                for lhs, key in pairs(originalKeysCache) do
                  -- only add the original keymaps if they are not already present
                  if
                    not vim.tbl_contains(
                      vim.tbl_map(function(k)
                        return k[1]
                      end, Keys),
                      lhs
                    )
                  then
                    Keys[#Keys + 1] = { lhs, table.unpack(key, 2) }
                  end
                end
              end
            end,
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
        tsserver_max_memory = 8192,
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
