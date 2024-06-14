return {
  "bennypowers/nvim-regexplainer",
  dependencies = {
    "MunifTanjim/nui.nvim",
  },
  opts = {
    auto = "true",
  },
  -- stylua: ignore
  keys = {
    {
      "<leader>r",
      function()
        require("regexplainer").show()
      end,
      desc = "Regexplainer",
    },
  },
}
