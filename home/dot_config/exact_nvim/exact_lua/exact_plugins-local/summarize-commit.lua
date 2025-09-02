local config_path = vim.fn.stdpath("config")

local sc = require("plugins-local-src.summarize-commit")

return {
  dir = config_path .. "/lua/plugins-local-src",
  ft = "gitcommit",
  keys = {
    {
      "<leader>ail",
      function()
        sc.summarize_commit_ollama()
      end,
      ft = "gitcommit",
      desc = "[Ollama] Summarize commit",
    },
    {
      "<leader>aic",
      function()
        sc.summarize_commit_cf()
      end,
      ft = "gitcommit",
      desc = "[CloudFlareAI] Summarize commit",
    },
  },
}
