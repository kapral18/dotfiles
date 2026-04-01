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
local function eslint_fix_all_async(bufnr)
  if not eslint_filetypes[vim.bo[bufnr].filetype] then
    return
  end

  local client = vim.lsp.get_clients({ bufnr = bufnr, name = "eslint" })[1]
  if not client then
    return
  end

  local version = (vim.lsp.util.buf_versions or {})[bufnr]

  client:request("workspace/executeCommand", {
    command = "eslint.applyAllFixes",
    arguments = {
      {
        uri = vim.uri_from_bufnr(bufnr),
        version = version,
      },
    },
  }, function(err)
    if err then
      return
    end
    -- Eslint fixes are semantic (unused vars, autofixable rules), not stylistic —
    -- prettier won't restyle them differently, so just save without re-formatting.
    vim.schedule(function()
      if vim.api.nvim_buf_is_valid(bufnr) and vim.bo[bufnr].modified then
        vim.api.nvim_buf_call(bufnr, function()
          vim.cmd("noautocmd silent! write")
        end)
        vim.b[bufnr].format_changedtick = vim.api.nvim_buf_get_changedtick(bufnr)
      end
    end)
  end, bufnr)
end

return {
  {
    "neovim/nvim-lspconfig",
    opts = {
      ---@type table<string, vim.lsp.Config>
      servers = {
        eslint = {
          root_dir = function(bufnr, on_dir)
            local fname = vim.api.nvim_buf_get_name(bufnr)
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
            local root = util.root_pattern(unpack(root_file))(fname)
            if root then
              on_dir(root)
            end
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
          -- Run eslint fixAll asynchronously after save to avoid blocking the UI.
          vim.api.nvim_create_autocmd("BufWritePost", {
            group = vim.api.nvim_create_augroup("k18_eslint_fix_all", { clear = true }),
            pattern = "*",
            callback = function(args)
              eslint_fix_all_async(args.buf)
            end,
          })
        end,
      },
    },
  },
}
