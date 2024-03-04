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

      require("which-key").register({
        m = {
          name = "+marks",
          t = { "<cmd>MarksToggleSigns<cr>", "toggle signs" },
          l = { "<cmd>MarksQFListAll<cr>", "list all marks" },
          b = { "<cmd>BookmarksQFListAll<cr>", "list all bookmarks" },
        },
      }, { prefix = "<leader>" })
    end,
  },
}
