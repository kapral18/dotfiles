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
      extra_text_objects = {
        "iq", "aq",
        "iv", "av",
        "ik", "ak",
        "ia", "aa",
        "ic", "ac", "iC", "aC",
        "id", "ad", "iD", "aD",
        "ie", "ae", "iE", "aE",
        "if", "af", "iF", "aF",
        "ig", "ag",
        "ih", "ah",
        "ii", "ai",
        "ij", "aj",
        "ik", "ak",
        "iL", "aL",
        "iN", "aN",
        "io", "ao",
        "iO", "aO",
        -- mixes up with leap irr mechanics so not using it
        -- leaving here as a warning
        -- "ir", "ar",
        "it", "at",
        "iu", "au",
        "iU", "aU",
        "iv", "av",
        "i$", "a$",
      },
      -- stylua: ignore end
    },
  },
}
