local common_utils = require("utils.common")
local sc = require("plugins-local-src.summarize-commit")

return {
  dir = common_utils.get_plugin_src_dir(),
  ft = "gitcommit",
  keys = {
    {
      "<leader>aisl",
      function()
        sc.summarize_commit_ollama()
      end,
      ft = "gitcommit",
      desc = "[Ollama] Summarize commit",
    },
    {
      "<leader>aisc",
      function()
        sc.summarize_commit_cf()
      end,
      ft = "gitcommit",
      desc = "[CloudFlareAI] Summarize commit",
    },
    {
      "<leader>aiso",
      function()
        sc.summarize_commit_openrouter()
      end,
      ft = "gitcommit",
      desc = "[OpenRouter] Summarize commit",
    },
  },
}
