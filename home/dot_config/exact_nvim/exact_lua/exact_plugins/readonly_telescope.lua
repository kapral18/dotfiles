return {
  {
    "nvim-telescope/telescope.nvim",
    cmd = "Telescope",
    opts = function()
      local actions = require("telescope.actions")
      return {
        defaults = {
          layout_config = {
            width = { padding = 0 },
            height = { padding = 0 },
            preview_height = 0.8,
          },
          layout_strategy = "vertical",
          mappings = {
            i = {
              ["<esc>"] = actions.close,
              ["<C-j>"] = actions.move_selection_next,
              ["<C-k>"] = actions.move_selection_previous,
            },
          },
        },
      }
    end,
  },
}
