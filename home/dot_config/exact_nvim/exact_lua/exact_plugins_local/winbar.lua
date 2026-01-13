local fs_util = require("util.fs")
local winbar = require("plugins_local_src.winbar")
vim.g.winbar_get_path = winbar.get_winbar_remainder_path

return {
  {
    dir = fs_util.get_plugin_src_dir(),
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
