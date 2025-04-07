local nvim_runtime_file = vim.api.nvim_get_runtime_file("", true)

table.insert(nvim_runtime_file, vim.env.VIMRUNTIME)

return {
  "neovim/nvim-lspconfig",
  opts = {
    servers = {
      lua_ls = {
        settings = {
          Lua = {
            workspace = {
              checkThirdParty = false,
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
