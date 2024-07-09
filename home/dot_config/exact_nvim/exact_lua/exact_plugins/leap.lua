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
    "ggandor/leap-spooky.nvim",
    opts = {
      paste_on_remote_yank = true,
      -- stylua: ignore start
      extra_text_objects = { "iq", "aq", "iv", "av", "ik", "ak" },
      -- stylua: ignore end
    },
  },
}
