return {
  {
    "smjonas/live-command.nvim",
    version = "*",
    config = function()
      require("live-command").setup({
        commands = {
          Norm = { cmd = "norm" },
          G = { cmd = "g" },
          V = { cmd = "v" },
          S = { cmd = "s" },
        },
      })
    end,
  },
}
