local fs_util = require("util.fs")
local sc = require("plugins_local_src.summarize-commit")

return {
  dir = fs_util.get_plugin_src_dir(),
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
