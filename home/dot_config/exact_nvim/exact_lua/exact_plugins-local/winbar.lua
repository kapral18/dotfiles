local config_path = vim.fn.stdpath("config")

local winbar = require("plugins-local-src.winbar")
vim.g.winbar_get_path = winbar.get_winbar_remainder_path

return {
  {
    dir = config_path .. "/lua/plugins-local-src",
    init = function()
      vim.opt.winbar = "%{v:lua.vim.g.winbar_get_path()}"
    end,
  },
  {
    "folke/snacks.nvim",
    opts = {
      terminal = {
        win = {
          wo = {
            winbar = "%{v:lua.vim.g.winbar_get_path()}",
          },
        },
      },
    },
  },
}
