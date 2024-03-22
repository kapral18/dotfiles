return {
  "stevearc/oil.nvim",
  dependencies = "nvim-tree/nvim-web-devicons",
  opts = {
    delete_to_trash = true,
    keymaps = {
      ["q"] = "actions.close",
    },
    lsp_file_methods = {
      autosave_changes = true,
    },
    experimental_watch_for_changes = true,
    view_options = {
      show_hidden = true,
    },
  },
  -- stylua: ignore
  keys = {
    { "<leader>;", function() require("oil").toggle_float() end, desc = "Toggle oil" },
  },
}
