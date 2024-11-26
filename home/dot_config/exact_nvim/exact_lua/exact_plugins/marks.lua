return {
  {
    "chentoast/marks.nvim",
    opts = {
      refresh_interval = 500,
    },
    config = function(_, opts)
      require("marks").setup(opts)

      require("which-key").add({
        { "m", group = "Marks", desc = "Set mark" },
        { "m]", desc = "Next mark" },
        { "m[", desc = "Previous mark" },
        { "m}", desc = "Next bookmark" },
        { "m{", desc = "Previous bookmark" },
        { "m,", desc = "Set next mark" },
        { "m;", desc = "Toggle mark" },
        { "m:", desc = "Preview mark" },
        { "m0", desc = "Set bookmark 0" },
        { "m1", desc = "Set bookmark 1" },
        { "m2", desc = "Set bookmark 2" },
        { "m3", desc = "Set bookmark 3" },
        { "m4", desc = "Set bookmark 4" },
        { "m5", desc = "Set bookmark 5" },
        { "m6", desc = "Set bookmark 6" },
        { "m7", desc = "Set bookmark 7" },
        { "m8", desc = "Set bookmark 8" },
        { "m9", desc = "Set bookmark 9" },
      })
    end,
  },
}
