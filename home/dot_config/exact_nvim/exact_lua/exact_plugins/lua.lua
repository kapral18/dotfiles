return {
  "neovim/nvim-lspconfig",
  dependencies = {
    "folke/lazydev.nvim", -- Ensure lazydev loads first
  },
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
