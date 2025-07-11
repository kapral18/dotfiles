local config_path = vim.fn.stdpath("config")

local sad = require("plugins-local-src.save-ai-data")

vim.api.nvim_create_user_command("SaveBufferToAIFile", function(opts)
  sad.save_buffer_to_ai_file(opts.fargs[1] == "append")
end, {
  desc = "Save current buffer content to ~/ai_data.txt",
  nargs = "?",
  complete = function()
    return { "append", "replace" }
  end,
})

return {
  dir = config_path .. "/lua/plugins-local-src",
  name = "save-ai-data",
  keys = {
    {
      "<leader>cc",
      "<cmd>SaveBufferToAIFile append<cr>",
      desc = "Save current buffer to ~/ai_data.txt (append)",
    },
    {
      "<leader>cC",
      "<cmd>SaveBufferToAIFile replace<cr>",
      desc = "Save current buffer to ~/ai_data.txt (replace)",
    },
  },
  cmd = {
    "SaveBufferToAIFile",
  },
}
