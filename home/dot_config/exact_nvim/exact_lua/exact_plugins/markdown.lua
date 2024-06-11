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
  { import = "lazyvim.plugins.extras.lang.markdown" },
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
}
