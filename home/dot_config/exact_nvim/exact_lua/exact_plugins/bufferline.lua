local Util = require("lazyvim.util")

return {
  "akinsho/bufferline.nvim",
  opts = {
    options = {
      separator_style = "slant",
    },
  },
  init = function()
    if Util.has("bufferline.nvim") then
      vim.keymap.set(
        "n",
        "<A-h>",
        Util.has("bufferline.nvim") and "<cmd>BufferLineCyclePrev<CR>" or ":bprevious<CR>",
        { noremap = true, silent = true, desc = "Previous buffer" }
      )
      vim.keymap.set(
        "n",
        "<A-l>",
        Util.has("bufferline.nvim") and "<cmd>BufferLineCycleNext<CR>" or ":bnext<CR>",
        { noremap = true, silent = true, desc = "Next buffer" }
      )
    end
  end,
}
