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
      model = "phind-codellama:latest",
    },
    config = function(_, opts)
      require("oatmeal").setup(opts)
      require("which-key").add({
        { "<leader>om", "<cmd>Oatmeal<CR>", desc = "[AI] Oatmeal: toggle", mode = { "n", "x" } },
      })
    end,
  },
  {
    "github/copilot.vim",
    lazy = false,
    init = function()
      vim.api.nvim_set_hl(0, "CopilotSuggestion", { fg = "#83a598" })
      vim.api.nvim_set_hl(0, "CopilotAnnotation", { fg = "#03a598" })
    end,
  },

  {
    "CopilotC-Nvim/CopilotChat.nvim",
    opts = {
      model = "o1-mini",
      temperature = 1,
    },
  },
}
