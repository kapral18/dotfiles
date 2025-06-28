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
              library = {
                string.format("%s/.hammerspoon/Spoons/EmmyLua.spoon/annotations", os.getenv("HOME")),
              },
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
              globals = { "vim", "hs", "spoon" },
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
