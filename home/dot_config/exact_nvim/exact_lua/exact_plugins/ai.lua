return {
  { import = "lazyvim.plugins.extras.coding.copilot-chat" },
  {
    "dustinblackman/oatmeal.nvim",
    event = "VeryLazy",
    cmd = { "Oatmeal" },
    dependencies = {
      "folke/which-key.nvim",
    },
    opts = {
      backend = "ollama",
      model = "llama3:latest",
    },
    config = function(_, opts)
      require("oatmeal").setup(opts)
      require("which-key").register({
        ["<leader>om"] = { "<cmd>Oatmeal<CR>", "[AI] Oatmeal: toggle", mode = { "n", "x" } },
      })
    end,
  },
  -- {
  --   "zbirenbaum/copilot.lua",
  --   event = "InsertEnter",
  --   opts = {
  --     filetypes = {
  --       ["*"] = function()
  --         local file_size = vim.fn.getfsize(vim.fn.expand("%"))
  --         if file_size > 100000 or file_size == -2 then
  --           return false
  --         end
  --         return true
  --       end,
  --     },
  --   },
  -- },
}
