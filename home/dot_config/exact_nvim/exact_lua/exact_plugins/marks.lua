return {
  {
    "chentoast/marks.nvim",
    opts = {
      default_mappings = true,
      builtin_marks = { ".", "^", "<", ">" },
      cyclic = true,
    },
    config = function()
      require("marks").setup({
        default_mappings = true,
        builtin_marks = { ".", "^", "<", ">" },
        cyclic = true,
      })

      require("which-key").add({
        { "<leader>m", group = "+marks" },
        { "<leader>t", "<cmd>MarksToggleSigns<cr>", desc = "toggle signs" },
        { "<leader>l", "<cmd>MarksQFListAll<cr>", desc = "list all marks" },
        { "<leader>b", "<cmd>BookmarksQFListAll<cr>", desc = "list all bookmarks" },
      })
    end,
  },
}
