return {
  {
    "L3MON4D3/LuaSnip",
    config = function(_, opts)
      require("luasnip").setup(opts)
      require("luasnip.loaders.from_vscode").lazy_load({ paths = vim.fn.stdpath("config") .. "/snippets" })
    end,
  },
  {
    "chrisgrieser/nvim-scissors",
    dependencies = {
      "rcarriga/nvim-notify",
    },
    opts = {
      jsonFormatter = "jq",
    },
    -- stylua: ignore
    keys = {
      { "<leader>aS", function() require("scissors").editSnippet() end, desc = "Edit Snippets" },
      { "<leader>as", mode = { "n", "v" }, function() require("scissors").addNewSnippet() end, desc = "Add Snippets" },
    },
  },
  {
    "folke/which-key.nvim",
    opts = {
      defaults = {
        ["<leader>a"] = { name = " annotation/snippets" },
      },
    },
  },
}
