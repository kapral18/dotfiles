return {
  {
    "mbbill/undotree",
    init = function()
      vim.g.undotree_CustomUndotreeCmd = "vertical 40 new"
      vim.g.undotree_CustomDiffpanelCmd = "botright 15 new"
    end,
    cmd = { "UndotreeShow", "UndotreeToggle" },
    keys = {
      { mode = "n", "<leader>uu", ":UndotreeToggle<CR>", { silent = true } },
    },
  },
  {
    "kevinhwang91/nvim-fundo",
    event = "BufReadPost",
    dependencies = { "kevinhwang91/promise-async" },
    opts = {},
    build = function()
      require("fundo").install()
    end,
  },
  {
    "pixelastic/vim-undodir-tree",
  },
}
