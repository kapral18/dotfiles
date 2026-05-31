return {
  {
    "nvim-telescope/telescope.nvim",
    -- Track master: telescope's semver-ish tags are stale (the `nvim-0.6` tag
    -- mis-sorts as newest under `version = "*"`, pinning a 2022 build that calls
    -- the removed `vim.treesitter.language.ft_to_lang` and crashes on nvim 0.12).
    version = false,
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
