return {
  {
    "ggandor/leap.nvim",
    enabled = true,
    keys = {
      { "s", mode = { "n", "x", "o" }, desc = "Leap forward to" },
      { "S", mode = { "n", "x", "o" }, desc = "Leap backward to" },
      { "gs", mode = { "n", "x", "o" }, desc = "Leap from windows" },
    },
    config = function(_, opts)
      local leap = require("leap")
      for k, v in pairs(opts) do
        leap.opts[k] = v
      end
      leap.add_default_mappings(true)
      vim.keymap.del({ "x", "o" }, "x")
      vim.keymap.del({ "x", "o" }, "X")
    end,
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
