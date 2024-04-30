return {
  {
    "danymat/neogen",
    opts = {
      snippet_engine = "luasnip",
      enabled = true,
    },
    -- stylua: ignore
    keys = {
      { "<leader>and", function() require("neogen").generate() end, desc = "Default Annotation" },
      { "<leader>anC", function() require("neogen").generate({ type = "class" }) end, desc = "Class" },
      { "<leader>anf", function() require("neogen").generate({ type = "func" }) end, desc = "Function" },
      { "<leader>ant", function() require("neogen").generate({ type = "type" }) end, desc = "Type" },
      { "<leader>anF", function() require("neogen").generate({ type = "file" }) end, desc = "File" },
    },
  },
  {
    "folke/which-key.nvim",
    opts = {
      defaults = {
        ["<leader>an"] = { name = " annotation/snippets" },
      },
    },
  },
  {
    "Zeioth/dooku.nvim",
    cmd = { "DookuGenerate", "DookuOpen", "DookuAutoSetup" },
    opts = {},
    -- stylua: ignore
    keys = {
      { "<leader>ang", "<Cmd>DookuGenerate<CR>", desc = "Generate HTML Docs" },
      { "<leader>ano", "<Cmd>DookuOpen<CR>", desc = "Open HTML Docs" },
    },
  },
}
