return {
  {
    "ggandor/leap.nvim",
    keys = {
      { "s", "<Plug>(leap-anywhere)", desc = "Leap" },
      {
        "gs",
        function()
          require("leap.remote").action()
        end,
        mode = { "n", "x", "o" },
        desc = "Leap remote action",
      },
    },
    config = true,
  },
  {
    "tpope/vim-abolish",
    init = function()
      vim.g.abolish_no_mappings = 1
    end,
  },
}
