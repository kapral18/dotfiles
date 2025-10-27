local util = require("util")
local sad = require("plugins_local_src.save-ai-data")

vim.api.nvim_create_user_command("SaveBufferToAIFile", function(opts)
  sad.save_buffer_to_ai_file(opts.fargs[1] == "append")
end, {
  desc = "Save current buffer content to ~/ai_data.txt",
  nargs = "?",
  complete = function()
    return { "append", "replace" }
  end,
})

vim.api.nvim_create_user_command("RemoveBufferFromAIFile", function()
  sad.remove_current_buffer_from_ai_file()
end, {
  desc = "Remove current buffer from ~/ai_data.txt",
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

vim.api.nvim_create_user_command("RemoveAIFileEntries", function(opts)
  local pattern = opts.fargs[1]
  if pattern then
    sad.remove_entries_by_pattern("custom", pattern)
  else
    vim.ui.input({
      prompt = "Enter pattern to remove: ",
    }, function(input_pattern)
      if input_pattern and input_pattern ~= "" then
        sad.remove_entries_by_pattern("custom", input_pattern)
      end
    end)
  end
end, {
  desc = "Remove entries from ai_data.txt by pattern",
  nargs = "?",
})

vim.api.nvim_create_user_command("RemoveAIFilesByType", function(opts)
  local type_options = { "source", "test", "config" }
  local file_type = opts.fargs[1]

  if file_type and vim.tbl_contains(type_options, file_type) then
    sad.remove_entries_by_pattern(file_type)
  else
    vim.ui.select(type_options, {
      prompt = "Select file type to remove:",
    }, function(choice)
      if choice then
        sad.remove_entries_by_pattern(choice)
      end
    end)
  end
end, {
  desc = "Remove entries from ai_data.txt by file type",
  nargs = "?",
  complete = function()
    return { "source", "test", "config" }
  end,
})

return {
  {
    dir = util.get_plugin_src_dir(),
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
      {
        "<leader>airp",
        "<cmd>RemoveAIFileEntries<cr>",
        desc = "Remove entries from ai_data.txt by pattern",
      },
      {
        "<leader>airb",
        "<cmd>RemoveBufferFromAIFile<cr>",
        desc = "Remove current buffer from ~/ai_data.txt",
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
                  -- Append mode with smart replacement
                  require("plugins_local_src.save-ai-data").save_path_to_ai_file(node.path, true)
                end
              end,
              desc = "Save node to AI file (append mode)",
            },
            ["<leader>aiS"] = {
              function(state)
                local node = state.tree:get_node()
                if node then
                  -- Replace mode with smart replacement
                  require("plugins_local_src.save-ai-data").save_path_to_ai_file(node.path, false)
                end
              end,
              desc = "Save node to AI file (replace mode)",
            },
            ["<leader>air"] = {
              function(state)
                local node = state.tree:get_node()
                if node then
                  require("plugins_local_src.save-ai-data").remove_path_from_ai_data(node.path)
                end
              end,
              desc = "Remove selected file/path from AI file",
            },
          },
        },
      },
    },
  },
}
