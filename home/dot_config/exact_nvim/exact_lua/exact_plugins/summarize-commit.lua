local config_path = vim.fn.stdpath("config")

return {
  dir = config_path .. "/lua/plugins-local",
  keys = {
    {
      "<leader>aid",
      function()
        require("plugins-local.summarize-commit").summarize_commit()
      end,
      desc = "Summarize commit",
    },
  },
}
