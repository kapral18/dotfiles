return {
  {
    "hedyhli/outline.nvim",
    cmd = { "Outline", "OutlineOpen" },
    keys = {
      { "<leader>cs", "<cmd>Outline<cr>", desc = "Toggle Outline" },
    },
    opts = {
      outline_window = {
        auto_open = false,
        show_numbers = false,
        show_relative_numbers = false,
      },
      guides = {
        enabled = true,
      },
    },
  },
}
