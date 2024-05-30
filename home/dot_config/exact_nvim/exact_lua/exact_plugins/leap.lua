return {
  {
    "ggandor/leap.nvim",
    keys = {
      { "<leader>lp", "<Plug>(leap)", desc = "Leap" },
      { "<leader>lP", "<Plug>(leap-from-window)", desc = "Leap from window" },
    },
    config = true,
  },
  {
    "shebpamm/leap-spooky.nvim",
    config = function()
      require("leap-spooky").setup({
        -- stylua: ignore start
        extra_text_objects = {
          "iq", "aq",
          "iv", "av",
          "ik", "ak",
        },
        -- stylua: ignore end
      })
    end,
  },
}
