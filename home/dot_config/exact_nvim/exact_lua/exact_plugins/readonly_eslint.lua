local format = require("util.format")

local eslint_filetypes = {
  javascript = true,
  javascriptreact = true,
  ["javascript.jsx"] = true,
  typescript = true,
  typescriptreact = true,
  ["typescript.tsx"] = true,
  vue = true,
  svelte = true,
  astro = true,
}

---@param bufnr number
local function eslint_fix_all(bufnr)
  local client = vim.lsp.get_clients({ bufnr = bufnr, name = "eslint" })[1]
  if not client then
    return
  end

  -- Keep parity with lspconfig's legacy `EslintFixAll` implementation.
  local versions = (vim.lsp.util and vim.lsp.util.buf_versions) or {}
  local version = versions[bufnr]

  client.request_sync("workspace/executeCommand", {
    command = "eslint.applyAllFixes",
    arguments = {
      {
        uri = vim.uri_from_bufnr(bufnr),
        version = version,
      },
    },
  }, 3000, bufnr)
end

return {
  {
    "neovim/nvim-lspconfig",
    opts = {
      ---@type table<string, vim.lsp.Config>
      servers = {
        eslint = {
          -- Nvim 0.11 uses `root_dir(bufnr, on_dir)`; older lspconfig-style configs use `root_dir(fname)`.
          root_dir = function(a, b)
            local fname ---@type string
            local on_dir ---@type fun(dir: string)|nil

            if type(a) == "number" and type(b) == "function" then
              fname = vim.api.nvim_buf_get_name(a)
              on_dir = b
            else
              fname = a
            end

            if type(fname) ~= "string" or fname == "" then
              return
            end

            local util = require("lspconfig.util")
            local root_file = {
              ".eslintrc",
              ".eslintrc.js",
              ".eslintrc.cjs",
              ".eslintrc.yaml",
              ".eslintrc.yml",
              ".eslintrc.json",
              "eslint.config.js",
              "eslint.config.mjs",
              "eslint.config.cjs",
              "eslint.config.ts",
              "eslint.config.mts",
              "eslint.config.cts",
            }
            root_file = util.insert_package_json(root_file, "eslintConfig", fname)
            -- Do not start eslint LSP just because we're in a git repo.
            -- Only enable it when an eslint config (or eslintConfig in package.json) exists.
            local root = util.root_pattern(unpack(root_file))(fname)
            if on_dir then
              if root then
                on_dir(root)
              end
              return
            end
            return root
          end,
          settings = {
            -- temporary until https://github.com/microsoft/vscode-eslint/pull/2076 is merged
            workingDirectory = { mode = "location" },
            codeActionOnSave = {
              enable = true,
              mode = "all",
            },
            format = true,
          },
        },
      },
      setup = {
        eslint = function()
          -- eslint fixes (applyAllFixes) are conceptually "formatting" for many workflows.
          -- Run these before conform / other formatters so the final formatter sees the updated buffer.
          format.register({
            name = "eslint: fixAll",
            primary = false,
            priority = 250,
            sources = function(bufnr)
              if not eslint_filetypes[vim.bo[bufnr].filetype] then
                return {}
              end
              local client = vim.lsp.get_clients({ bufnr = bufnr, name = "eslint" })[1]
              return client and { "eslint.applyAllFixes" } or {}
            end,
            format = eslint_fix_all,
          })
        end,
      },
    },
  },
}
