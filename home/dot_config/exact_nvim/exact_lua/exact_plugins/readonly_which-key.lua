return {
  {
    "folke/which-key.nvim",
    opts = {
      preset = "modern",
    },
    config = function(_, opts)
      require("which-key").setup(opts)
    end,
  },
}
