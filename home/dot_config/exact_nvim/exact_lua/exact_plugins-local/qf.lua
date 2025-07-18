local config_path = vim.fn.stdpath("config")

local qf = require("plugins-local-src.qf")

return {
  {
    "romainl/vim-qf",
    lazy = false,
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
    dir = config_path .. "/lua/plugins-local-src",
    keys = {
      {
        "<leader>rqi",
        function()
          local pattern = vim.fn.input("Pattern(include): ")

          if pattern then
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
            qf.filter_qf_items_by_pattern(pattern, true)
          else
            print("No pattern provided")
          end
        end,
        desc = "Exclude Quickfix Items by Pattern",
      },
      {
        "dd",
        function()
          qf.remove_qf_item()
        end,
        desc = "Remove Quickfix Item",
        ft = { "qf" },
      },
    },
  },
}
