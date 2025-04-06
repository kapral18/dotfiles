return {
  {
    "BrunoKrugel/lazydocker.nvim",
    cmd = "LazyDocker",
    dependencies = {
      "nvim-lua/plenary.nvim",
    },
    keys = {
      {
        "<leader>ld",
        "<cmd>LazyDocker<cr>",
        desc = "Open LazyDocker",
      },
    },
  },
}
