return {
  {
    "folke/noice.nvim",
    opts = {
      lsp = {
        signature = {
          enabled = false,
        },
      },
    },
  },
  {
    "ray-x/lsp_signature.nvim",
    event = "BufRead",
    config = function(_, opts)
      require("lsp_signature").on_attach()
      require("lsp_signature").setup(opts)
    end,
  },
}
