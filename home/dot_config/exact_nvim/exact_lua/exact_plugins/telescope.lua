return {
  {
    "nvim-telescope/telescope.nvim",
    opts = {
      defaults = {
        layout_config = {
          width = { padding = 0 },
          height = { padding = 0 },
          preview_height = 0.8,
        },
        layout_strategy = "vertical",
        mappings = {
          i = {
            ["<esc>"] = require("telescope.actions").close,
            ["<C-j>"] = require("telescope.actions").move_selection_next,
            ["<C-k>"] = require("telescope.actions").move_selection_previous,
          },
        },
      },
    },
  },
}
