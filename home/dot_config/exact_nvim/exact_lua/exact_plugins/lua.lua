local nvim_runtime_file = vim.api.nvim_get_runtime_file("", true)

table.insert(nvim_runtime_file, vim.env.VIMRUNTIME)

return {
  "neovim/nvim-lspconfig",
  dependencies = {
    { "antosha417/nvim-lsp-file-operations", config = true },
  },
  opts = {
    inlay_hints = {
      enabled = false,
    },
    servers = {
      lua_ls = {
        settings = {
          Lua = {
            workspace = {
              checkThirdParty = false,
              library = nvim_runtime_file,
            },
            completion = {
              callSnippet = "Replace",
            },
            runtime = {
              version = "LuaJIT",
            },
            hint = {
              enable = true,
              setType = true,
            },
            diagnostics = {
              globals = { "vim" },
            },
            telemetry = {
              enable = false,
            },
          },
        },
      },
    },
  },
}
