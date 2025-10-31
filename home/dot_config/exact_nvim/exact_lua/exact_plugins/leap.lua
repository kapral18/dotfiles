return {
  {
    "rasulomaroff/telepath.nvim",
    dependencies = {
      {
        "ggandor/leap.nvim",
        keys = {
          { "s", "<Plug>(leap)", desc = "Leap" },
          { "gs", "<Plug>(leap-from-window)", desc = "Leap from window" },
        },
        config = true,
      },
      {
        "tpope/vim-abolish",
        init = function()
          vim.g.abolish_no_mappings = 1
        end,
      },
    },
    config = function()
      require("telepath").use_default_mappings()
    end,
  },
}
