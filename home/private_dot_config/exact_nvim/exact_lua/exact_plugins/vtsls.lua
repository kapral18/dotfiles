-- @opts table
-- @opts.command string
-- @opts.arguments table
-- @opts.on_result function
local function lsp_execute(opts)
  local clients = vim.lsp.get_clients({ bufnr = 0, name = "vtsls" })
  local vtsls_client = nil
  for _, client in ipairs(clients) do
    if client.name == "vtsls" then
      vtsls_client = client
      break
    end
  end

  if vtsls_client then
    local params = {
      command = opts.command,
      arguments = opts.arguments,
    }

    vtsls_client.request("workspace/executeCommand", params, function(err, result, ctx)
      if err then
        vim.notify("Error executing command: " .. vim.inspect(err), vim.log.levels.ERROR)
      else
        if opts.on_result ~= nil then
          opts.on_result(result)
        end
      end
    end)
  else
    vim.notify("vtsls client not found", vim.log.levels.WARN)
  end
end

-- @opts table
-- @opts.command string
-- @opts.arguments table
local function lsp_execute_to_qf(opts)
  lsp_execute({
    command = opts.command,
    arguments = opts.arguments,
    on_result = function(result)
      if result and #result > 0 then
        local qf_list = {}
        for _, item in ipairs(result) do
          table.insert(qf_list, {
            filename = vim.uri_to_fname(item.uri),
            lnum = item.range.start.line + 1,
            col = item.range.start.character + 1,
            text = item.lineText,
          })
        end
        vim.fn.setqflist(qf_list, "r")
        vim.cmd("copen")
        vim.notify("File references found and added to quickfix list", vim.log.levels.INFO)
      else
        vim.notify("No file references found", vim.log.levels.INFO)
      end
    end,
  })
end

local function lsp_action(action)
  vim.lsp.buf.code_action({
    apply = true,
    context = {
      only = { action },
      diagnostics = {},
    },
  })
end

local M = {
  {
    "neovim/nvim-lspconfig",
    opts = {
      servers = {
        tsserver = {
          enabled = false,
        },
        ts_ls = {
          enabled = false,
        },
        vtsls = {
          filetypes = {
            "javascript",
            "jsx",
            "tsx",
            "javascriptreact",
            "javascript.jsx",
            "typescript",
            "typescriptreact",
            "typescript.tsx",
          },
          settings = {
            complete_function_calls = false,
            vtsls = {
              enableMoveToFileCodeAction = true,
              autoUseWorkspaceTsdk = true,
              experimental = {
                completion = {
                  enableServerSideFuzzyMatch = true,
                },
              },
            },
            typescript = {
              updateImportsOnFileMove = { enabled = "always" },
              suggest = {
                completeFunctionCalls = false,
              },
              tsserver = {
                maxTsServerMemory = 32000,
              },
              preferences = {
                includePackageJsonAutoImports = "on",
                preferTypeOnlyAutoImports = true,
              },
            },
          },
          root_dir = function()
            return vim.fn.getcwd()
          end,
          keys = {
            {
              "gD",
              function()
                local params = vim.lsp.util.make_position_params(0, "utf-8")

                lsp_execute_to_qf({
                  command = "typescript.goToSourceDefinition",
                  arguments = {
                    params.textDocument.uri,
                    params.position,
                  },
                })
              end,
              desc = "Goto Source Definition",
            },
            {
              "gR",
              function()
                lsp_execute_to_qf({
                  command = "typescript.findAllFileReferences",
                  arguments = { vim.uri_from_bufnr(0) },
                })
              end,
              desc = "File References",
            },
            {
              "<leader>co",
              function()
                lsp_action("source.organizeImports")
              end,
              desc = "Organize Imports",
            },
            {
              "<leader>cM",
              function()
                lsp_action("source.addMissingImports.ts")
              end,
              desc = "Add missing imports",
            },
            {
              "<leader>cu",
              function()
                lsp_action("source.removeUnused.ts")
              end,
              desc = "Remove unused imports",
            },
            {
              "<leader>cD",
              function()
                lsp_action("source.fixAll.ts")
              end,
              desc = "Fix all diagnostics",
            },
            {
              "<leader>cV",
              function()
                lsp_execute({ command = "typescript.selectTypeScriptVersion" })
              end,
              desc = "Select TS workspace version",
            },
            {
              "gl",
              function()
                local clients = vim.lsp.get_clients({ bufnr = 0, name = "vtsls" })
                local vtsls_client = nil
                for _, client in ipairs(clients) do
                  if client.name == "vtsls" then
                    vtsls_client = client
                    break
                  end
                end

                if vtsls_client then
                  local capabilities = vtsls_client.server_capabilities

                  local lines = {}

                  -- Add executeCommandProvider information
                  table.insert(lines, "")
                  table.insert(lines, "Execute Command Provider:")
                  if capabilities.executeCommandProvider then
                    local commands = capabilities.executeCommandProvider.commands
                    if commands and #commands > 0 then
                      table.insert(lines, "Supported commands:")
                      for _, command in ipairs(commands) do
                        table.insert(lines, "  - " .. command)
                      end
                    else
                      table.insert(lines, "No specific commands listed")
                    end
                  else
                    table.insert(lines, "Not supported by this LSP server")
                  end

                  table.insert(lines, "")
                  table.insert(lines, "Code Action Provider:")
                  if capabilities.codeActionProvider then
                    local codeActionKinds = capabilities.codeActionProvider.codeActionKinds
                    if codeActionKinds then
                      for _, kind in ipairs(codeActionKinds) do
                        table.insert(lines, "- " .. kind)
                      end
                    else
                      table.insert(lines, "- All code actions are supported (no specific kinds listed)")
                    end
                  end

                  vim.lsp.util.open_floating_preview(lines, "markdown", { border = "single" })
                end
              end,
              desc = "Show supported LSP actions",
            },
          },
        },
      },
      setup = {
        --- @deprecated -- tsserver renamed to ts_ls but not yet released, so keep this for now
        --- the proper approach is to check the nvim-lspconfig release version when it's released to determine the server name dynamically
        tsserver = function()
          -- disable tsserver
          return true
        end,
        ts_ls = function()
          -- disable tsserver
          return true
        end,
        vtsls = function(_, opts)
          vim.api.nvim_create_autocmd("LspAttach", {
            -- @param args table
            -- @param args.buf number
            -- @param args.data table
            -- @param args.data.client_id number
            callback = function(args)
              local client = vim.lsp.get_client_by_id(args.data.client_id)
              if client and client.name == "vtsls" then
                client.commands["_typescript.moveToFileRefactoring"] = function(command, ctx)
                  ---@type string, string, lsp.Range
                  local action, uri, range = unpack(command.arguments)

                  local function move(newf)
                    client.request("workspace/executeCommand", {
                      command = command.command,
                      arguments = { action, uri, range, newf },
                    })
                  end

                  local fname = vim.uri_to_fname(uri)
                  client.request("workspace/executeCommand", {
                    command = "typescript.tsserverRequest",
                    arguments = {
                      "getMoveToRefactoringFileSuggestions",
                      {
                        file = fname,
                        startLine = range.start.line + 1,
                        startOffset = range.start.character + 1,
                        endLine = range["end"].line + 1,
                        endOffset = range["end"].character + 1,
                      },
                    },
                  }, function(_, result)
                    ---@type string[]
                    local files = result.body.files
                    table.insert(files, 1, "Enter new path...")
                    vim.ui.select(files, {
                      prompt = "Select move destination:",
                      format_item = function(f)
                        return vim.fn.fnamemodify(f, ":~:.")
                      end,
                    }, function(f)
                      if f and f:find("^Enter new path") then
                        vim.ui.input({
                          prompt = "Enter move destination:",
                          default = vim.fn.fnamemodify(fname, ":h") .. "/",
                          completion = "file",
                        }, function(newf)
                          return newf and move(newf)
                        end)
                      elseif f then
                        move(f)
                      end
                    end)
                  end)
                end
              end
            end,
          })

          -- copy typescript settings to javascript
          opts.settings.javascript =
            vim.tbl_deep_extend("force", {}, opts.settings.typescript, opts.settings.javascript or {})
        end,
      },
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
              LazyVim.get_pkg_path("js-debug-adapter", "/js-debug/src/dapDebugServer.js"),
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

      local js_filetypes = { "typescript", "javascript", "typescriptreact", "javascriptreact" }

      local vscode = require("dap.ext.vscode")
      vscode.type_to_filetypes["node"] = js_filetypes
      vscode.type_to_filetypes["pwa-node"] = js_filetypes

      for _, language in ipairs(js_filetypes) do
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

  -- Filetype icons
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

return {}
