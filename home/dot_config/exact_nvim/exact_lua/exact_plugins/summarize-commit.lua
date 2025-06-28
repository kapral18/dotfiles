local config_path = vim.fn.stdpath("config")

return {
  dir = config_path .. "/lua/plugins-local",
  ft = "gitcommit",
  keys = {
    {
      "<leader>ail",
      function()
        require("plugins-local.summarize-commit").summarize_commit_ollama()
      end,
      ft = "gitcommit",
      desc = "[Ollama] Summarize commit",
    },
    {
      "<leader>aic",
      function()
        require("plugins-local.summarize-commit").summarize_commit_cf()
      end,
      ft = "gitcommit",
      desc = "[CloudFlareAI] Summarize commit",
    },
  },
}
