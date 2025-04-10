return {
  {
    "gcavallanti/vim-noscrollbar",
    lazy = false,
    dependencies = {
      "nvim-lualine/lualine.nvim",
      opts = {
        sections = {
          lualine_y = { "%{noscrollbar#statusline(20,'■','◫',['◧'],['◨'])}" },
        },
        always_show_tabline = false,
      },
    },
  },
}
