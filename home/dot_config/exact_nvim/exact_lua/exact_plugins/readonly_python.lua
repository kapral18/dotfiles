vim.g.python_lsp = "basedpyright"
vim.g.python_ruff = vim.g.python_ruff or "ruff"

local python_lsp = vim.g.python_lsp or "pyright"
local python_ruff = vim.g.python_ruff or "ruff"

local test_term = nil

return {
  {
    "nvim-treesitter/nvim-treesitter",
    opts = function(_, opts)
      opts.ensure_installed = vim.list_extend(opts.ensure_installed or {}, { "python", "requirements" })
      return opts
    end,
  },
  {
    "neovim/nvim-lspconfig",
    opts = function(_, opts)
      opts.servers = opts.servers or {}
      opts.servers[python_lsp] = vim.tbl_deep_extend("force", {
        settings = {},
      }, opts.servers[python_lsp] or {})
      opts.servers[python_ruff] = vim.tbl_deep_extend("force", {
        keys = {
          {
            "<leader>co",
            function()
              vim.lsp.buf.code_action({
                context = {
                  only = { "source.organizeImports" },
                  diagnostics = {},
                },
              })
            end,
            desc = "Organize Imports",
          },
        },
      }, opts.servers[python_ruff] or {})

      opts.setup = opts.setup or {}
      local handler = opts.setup[python_ruff]
      opts.setup[python_ruff] = function(_, server_opts)
        if handler and handler(_, server_opts) then
          return true
        end
        require("snacks").util.lsp.on({ name = python_ruff }, function(_, client)
          client.server_capabilities.hoverProvider = false
        end)
      end

      for _, server in ipairs({ "pyright", "basedpyright", "ruff", "ruff_lsp" }) do
        if opts.servers[server] then
          opts.servers[server].enabled = server == python_lsp or server == python_ruff
        end
      end
    end,
  },
  {
    "mason-org/mason.nvim",
    opts = function(_, opts)
      opts.ensure_installed = vim.list_extend(opts.ensure_installed or {}, { "ruff" })
      return opts
    end,
  },
  {
    "stevearc/conform.nvim",
    opts = function(_, opts)
      opts.formatters_by_ft = vim.tbl_deep_extend("force", opts.formatters_by_ft or {}, {
        python = { "ruff_fix", "ruff_format" },
      })
      return opts
    end,
  },
  -- Lightweight Test Runners using Snacks
  {
    "folke/snacks.nvim",
    opts = function(_, opts)
      return opts
    end,
    keys = {
      {
        "<leader>tt",
        function()
          local file = vim.fn.expand("%")
          local is_test = string.match(file, "test")
          local cmd = ""

          -- Try to find focused test
          local func_name, class_name
          local node = vim.treesitter.get_node()
          while node do
            if node:type() == "function_definition" then
              local name_node = node:field("name")[1]
              if name_node then
                local name = vim.treesitter.get_node_text(name_node, 0)
                if name:match("^test") then
                  func_name = name
                  -- Look for parent class
                  local p = node:parent()
                  while p do
                    if p:type() == "class_definition" then
                      local cname_node = p:field("name")[1]
                      if cname_node then
                        class_name = vim.treesitter.get_node_text(cname_node, 0)
                      end
                      break
                    end
                    p = p:parent()
                  end
                end
              end
              break
            end
            node = node:parent()
          end

          if vim.fn.executable("pytest") == 1 then
            cmd = "pytest --color=yes " .. file
            if func_name then
              if class_name then
                cmd = cmd .. "::" .. class_name .. "::" .. func_name
              else
                cmd = cmd .. "::" .. func_name
              end
            end
          elseif is_test then
            cmd = "python3 " .. file
            if func_name then
              if class_name then
                cmd = cmd .. " " .. class_name .. "." .. func_name
              else
                cmd = cmd .. " " .. func_name
              end
            end
            cmd = cmd .. " -v"

            -- Add basic coloring for unittest output
            cmd = cmd .. " 2>&1 | sed -e 's/OK/" .. [[\x1b[32mOK\x1b[0m]] .. "/' "
            cmd = cmd .. "-e 's/ok$/" .. [[\x1b[32mok\x1b[0m]] .. "/' "
            cmd = cmd .. "-e 's/FAILED/" .. [[\x1b[31mFAILED\x1b[0m]] .. "/' "
            cmd = cmd .. "-e 's/FAIL$/" .. [[\x1b[31mFAIL\x1b[0m]] .. "/' "
            cmd = cmd .. "-e 's/FAIL:/" .. [[\x1b[31mFAIL:\x1b[0m]] .. "/' "
            cmd = cmd .. "-e 's/ERROR/" .. [[\x1b[31mERROR\x1b[0m]] .. "/'"
          else
            cmd = "python3 " .. file
          end

          -- Run in split using our utility
          require("util.terminal").run_in_split(cmd, { focus_original = true })
        end,
        desc = "Run Python File",
        ft = "python",
      },
      {
        "<leader>td",
        function()
          -- Requires nvim-dap-python setup elsewhere or manual invocation
          vim.notify("Debug not configured. Install nvim-dap-python.", vim.log.levels.WARN)
        end,
        desc = "Debug Python Test",
        ft = "python",
      },
    },
  },
}
