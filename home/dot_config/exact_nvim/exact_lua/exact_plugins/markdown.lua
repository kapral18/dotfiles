-- vim.filetype.add({
--   extension = {
--     mdx = "jsx",
--   },
-- })

return {
  -- {
  --   "williamboman/mason.nvim",
  --   opts = function(_, opts)
  --     vim.list_extend(opts.ensure_installed, {
  --       "mdx-analyzer",
  --     })
  --   end,
  -- },
  {
    "lukas-reineke/headlines.nvim",
    enabled = false,
  },
  {
    "plasticboy/vim-markdown",
    dependencies = {
      "godlygeek/tabular",
      opt = true,
    },
    ft = "markdown",
  },
  {
    "kiran94/edit-markdown-table.nvim",
    config = true,
    dependencies = { "nvim-treesitter/nvim-treesitter" },
    cmd = "EditMarkdownTable",
  },
  {
    "gaoDean/autolist.nvim",
    ft = {
      "markdown",
      "text",
      "tex",
      "plaintex",
      "norg",
    },
    opts = {},
    keys = {
      { "<tab>", "<cmd>AutolistTab<cr>", mode = { "i" } },
      { "<s-tab>", "<cmd>AutolistShiftTab<cr>", mode = { "i" } },
      { "<CR>", "<CR><cmd>AutolistNewBullet<cr>", mode = { "i" } },
      { "o", "o<cmd>AutolistNewBullet<cr>", mode = { "n" } },
      { "O", "O<cmd>AutolistNewBulletBefore<cr>", mode = { "n" } },
      { "<CR>", "<cmd>AutolistToggleCheckbox<cr><CR>", mode = { "n" } },
      { "<C-r>", "<cmd>AutolistRecalculate<cr>", mode = { "n" } },

      { "].", "<cmd>AutolistCycleNext<cr>", mode = { "n" }, desc = "Next List Type" },
      { "[.", "<cmd>AutolistCyclePrev<cr>", mode = { "n" }, desc = "Prev List Type" },

      { ">>", ">><cmd>AutolistRecalculate<cr>", mode = { "n" } },
      { "<<", "<<<cmd>AutolistRecalculate<cr>", mode = { "n" } },
      { "dd", "dd<cmd>AutolistRecalculate<cr>", mode = { "n" } },
      { "d", "d<cmd>AutolistRecalculate<cr>", mode = { "v" } },
    },
  },
}
