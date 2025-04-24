return {
  {
    "ggandor/leap.nvim",
    keys = {
      { "s", "<Plug>(leap)", desc = "Leap" },
      { "gs", "<Plug>(leap-from-window)", desc = "Leap from window" },
    },
    config = true,
  },
  {
    "rasulomaroff/telepath.nvim",
    dependencies = "ggandor/leap.nvim",
    lazy = false,
    config = function()
      require("telepath").use_default_mappings()
    end,
  },
}
