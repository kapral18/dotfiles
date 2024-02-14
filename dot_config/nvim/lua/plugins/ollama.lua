return {
  "David-Kunz/gen.nvim",
  lazy = false,
  keys = {
    { "<leader>olm", ":Gen<CR>", mode = { "n", "v", "x" }, desc = "[O][l]lama: [M]enu" },
    {
      "<leader>ols",
      function()
        require("gen").select_model()
      end,
      mode = { "n" },
      desc = "[O[l]lama: [S]elect Model",
    },
  },
  opts = {
    model = "magicoder",
    display_mode = "float",
    show_model = true,
  },
}
