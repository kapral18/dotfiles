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

vim.api.nvim_create_user_command("SavePathToAIFile", function(opts)
  local path = opts.fargs[1] or vim.fn.getcwd()
  local mode = opts.fargs[2] or "append"
  sad.save_path_to_ai_file(path, mode == "append")
end, {
  desc = "Save file/folder content to ~/ai_data.txt with filtering options",
  nargs = "*",
  complete = function(arg_lead, cmd_line, cursor_pos)
    local args = vim.split(cmd_line, "%s+")
    if #args <= 2 then
      return vim.fn.getcompletion(arg_lead, "file")
    elseif #args == 3 then
      return { "append", "replace" }
    end
    return {}
  end,
})

return {
  {
    dir = config_path .. "/lua/plugins-local-src",
    name = "save-ai-data",
    keys = {
      {
        "<leader>ais",
        "<cmd>SaveBufferToAIFile append<cr>",
        desc = "Save current buffer to ~/ai_data.txt (append)",
      },
      {
        "<leader>aiS",
        "<cmd>SaveBufferToAIFile replace<cr>",
        desc = "Save current buffer to ~/ai_data.txt (replace)",
      },
    },
  },
  {
    "nvim-neo-tree/neo-tree.nvim",
    opts = {
      filesystem = {
        window = {
          mappings = {
            ["<leader>ais"] = {
              function(state)
                local node = state.tree:get_node()
                if node then
                  -- Append mode
                  require("plugins-local-src.save-ai-data").save_path_to_ai_file(node.path, true)
                end
              end,
              desc = "Save node to AI file (append mode)",
            },
            ["<leader>aiS"] = {
              function(state)
                local node = state.tree:get_node()
                if node then
                  -- Replace mode
                  require("plugins-local-src.save-ai-data").save_path_to_ai_file(node.path, false)
                end
              end,
              desc = "Save node to AI file (replace mode)",
            },
          },
        },
      },
    },
  },
}
