return {
  {
    "danymat/neogen",
    opts = {
      snippet_engine = "luasnip",
      enabled = true,
    },
    dependencies = { "hrsh7th/nvim-cmp", "L3MON4D3/LuaSnip", "folke/which-key.nvim" },
    config = function(_, opts)
      require("neogen").setup(opts)
      require("which-key").register({
        ["<leader>n"] = {
          name = " annotation",
          d = { "<Cmd>lua require('neogen').generate({})<CR>", "Default Annotation" },
          c = { "<Cmd>lua require('neogen').generate({ type = 'class' })<CR>", "Class" },
          f = { "<Cmd>lua require('neogen').generate({ type = 'func' })<CR>", "Function" },
          t = { "<Cmd>lua require('neogen').generate({ type = 'type' })<CR>", "Type" },
          F = { "<Cmd>lua require('neogen').generate({ type = 'file' })<CR>", "File" },
        },
      })
    end,
  },
  {
    "Zeioth/dooku.nvim",
    cmd = { "DookuGenerate", "DookuOpen", "DookuAutoSetup" },
    opts = {},
    -- stylua: ignore
    keys = {
      { "<leader>ng", "<Cmd>DookuGenerate<CR>", desc = "Generate HTML Docs" },
    },
  },
}
