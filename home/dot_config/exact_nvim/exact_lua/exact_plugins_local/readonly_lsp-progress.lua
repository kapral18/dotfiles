return {
  name = "k18-lsp-progress",
  dependencies = {
    "nvim-lualine/lualine.nvim",
  },
  config = function()
    require("plugins_local_src.lsp-progress").setup()
  end,
}
