local ft = {
  "markdown",
  "text",
  "tex",
  "plaintex",
  "norg",
}
return {
  {
    "gaoDean/autolist.nvim",
    ft = ft,
    opts = {},
    keys = {
      { "<tab>", "<cmd>AutolistTab<cr>", mode = "i", desc = "[AutoList] Tab [i]", ft = ft },
      { "<s-tab>", "<cmd>AutolistShiftTab<cr>", mode = "i", desc = "[AutoList] S-Tab [i]", ft = ft },
      { "<CR>", "<CR><cmd>AutolistNewBullet<cr>", mode = "i", desc = "[AutoList] New Bullet [i]", ft = ft },
      { "o", "o<cmd>AutolistNewBullet<cr>", mode = "n", desc = "[AutoList] New Bullet", ft = ft },
      { "O", "O<cmd>AutolistNewBulletBefore<cr>", mode = "n", desc = "[Autolist] New Bullet Before", ft = ft },
      { "<CR>", "<cmd>AutolistToggleCheckbox<cr><CR>", mode = "n", desc = "[AutoLost] Toggle Checkbox", ft = ft },
      { "<C-r>", "<cmd>AutolistRecalculate<cr>", mode = "n", desc = "[AutoList] Recalculate", ft = ft },

      { "].", "<cmd>AutolistCycleNext<cr>", mode = "n", desc = "[AutoList] Next List Type", ft = ft },
      { "[.", "<cmd>AutolistCyclePrev<cr>", mode = "n", desc = "[AutoList] Prev List Type", ft = ft },

      { ">>", ">><cmd>AutolistRecalculate<cr>", mode = "n", desc = "[Autolist] >> Recalculate", ft = ft },
      { "<<", "<<<cmd>AutolistRecalculate<cr>", mode = "n", desc = "[Autolist] << Recalculate", ft = ft },
      { "dd", "dd<cmd>AutolistRecalculate<cr>", mode = "n", desc = "[Autolist] dd Recalculate", ft = ft },
      { "d", "d<cmd>AutolistRecalculate<cr>", mode = "v", desc = "[AutoList] Recalculate [v]", ft = ft },
    },
  },
}
