return {
  {
    "folke/lazydev.nvim",
    ft = "lua",
    opts = {
      library = {
        {
          path = "plenary.nvim",
          words = {
            "before_each",
            "after_each",
            "describe",
            "it",
            "pending",
            "clear",
          },
        },
      },
    },
  },
}
