local common_utils = require("utils.common")
local winbar = require("plugins-local-src.winbar")
vim.g.winbar_get_path = winbar.get_winbar_remainder_path

return {
  {
    dir = common_utils.get_plugin_src_dir(),
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
