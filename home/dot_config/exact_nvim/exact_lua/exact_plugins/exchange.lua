local function exchange()
  return require("substitute.exchange")
end

return {
  {
    "gbprod/substitute.nvim",
    keys = {
      -- stylua: ignore start
      { "<leader>X", function() exchange().operator() end, desc = "exchange operator" },
      { "<leader>Xx", function() exchange().line() end, desc = "exchange the line" },
      { "<leader>X", function() exchange().visual() end, desc = "exchange operator", mode = "x" },
      { "<leader>Xc", function() exchange().cancel() end, desc = "cancel exchange" },
      -- stylua: ignore end
    },
    config = true,
  },
  {
    "folke/which-key.nvim",
    opts = {
      defaults = {
        ["<leader>X"] = { name = "exchange" },
      },
    },
  },
}
