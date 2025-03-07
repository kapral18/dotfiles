local config_path = vim.fn.stdpath("config")

return {
  {
    "romainl/vim-qf",
    init = function()
      -- enable ack style mappings
      vim.g.qf_mapping_ack_style = 1
      -- disable auto quit if qf window is the only window
      vim.g.qf_auto_quit = 0
      -- if the path is too long, shorten each component to the first 3 chars
      vim.g.qf_shorten_path = 3
      -- disable auto resize
      vim.g.qf_auto_resize = 0
    end,
  },
  {
    dir = config_path .. "/lua/plugins-local",
    keys = {
      {
        "<leader>rqi",
        function()
          local pattern = vim.fn.input("Pattern(include): ")

          if pattern then
            local qf = require("plugins-local.qf")

            qf.filter_qf_items_by_pattern(pattern, false)
          else
            print("No pattern provided")
          end
        end,
        desc = "Filter Quickfix Items by Pattern",
      },
      {
        "<leader>rqx",
        function()
          local pattern = vim.fn.input("Pattern(exclude): ")

          if pattern then
            local qf = require("plugins-local.qf")

            qf.filter_qf_items_by_pattern(pattern, true)
          else
            print("No pattern provided")
          end
        end,
        desc = "Exclude Quickfix Items by Pattern",
      },
    },
    config = function()
      local owner_folder_search = require("plugins-local.owner-folder-search").owner_folder_search

      vim.api.nvim_create_user_command("OwnerFolderSearch", owner_folder_search, {
        nargs = "+",
        desc = "Search owned directories from CODEOWNERS with ripgrep",
      })
    end,
  },
}
