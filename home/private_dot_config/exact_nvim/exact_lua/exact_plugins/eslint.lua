local function fix_all(opts)
  local util = require("lspconfig.util")

  opts = opts or {}

  local eslint_lsp_client = util.get_active_client_by_name(opts.bufnr, "eslint")
  if eslint_lsp_client == nil then
    return
  end

  local request
  if opts.sync then
    request = function(bufnr, method, params)
      eslint_lsp_client.request_sync(method, params, nil, bufnr)
    end
  else
    request = function(bufnr, method, params)
      eslint_lsp_client.request(method, params, nil, bufnr)
    end
  end

  local bufnr = util.validate_bufnr(opts.bufnr or 0)
  request(0, "workspace/executeCommand", {
    command = "eslint.applyAllFixes",
    arguments = {
      {
        uri = vim.uri_from_bufnr(bufnr),
        version = vim.lsp.util.buf_versions[bufnr],
      },
    },
  })
end

return {
  {
    "neovim/nvim-lspconfig",
    opts = {
      servers = {
        eslint = {
          settings = {
            -- helps eslint find the eslintrc when it's placed in a subfolder instead of the cwd root
            workingDirectories = { mode = "auto" },
            codeActionOnSave = {
              enable = false,
            },
            format = false,
          },
        },
      },
      setup = {
        eslint = function()
          local function get_client(buf)
            return LazyVim.lsp.get_clients({ name = "eslint", bufnr = buf })[1]
          end

          local formatter = LazyVim.lsp.formatter({
            name = "eslint: EslintFixAll",
            primary = false,
            priority = 200,
            filter = "eslint",
            sources = function(buf)
              local client = get_client(buf)
              return client and { "eslint" } or {}
            end,
            format = function(buf)
              fix_all({ bufnr = buf, sync = true })
            end,
          })

          -- register the formatter with LazyVim
          LazyVim.format.register(formatter)
        end,
      },
    },
  },
}
