return {
  {
    "folke/snacks.nvim",
    opts = {
      bigfile = { enabled = false },
      -- indent = { enabled = false },
      input = { enabled = false },
      notifier = { enabled = true },
      scope = { enabled = false },
      scroll = { enabled = false },
      statuscolumn = { enabled = false }, -- lazyvim handles that
      toggle = { enabled = false },
      words = { enabled = false },
    },
    keys = {
      {
        "<leader>n",
        false,
      },
      {
        "<leader>un",
        false,
      },
      {
        "<leader>nh",
        function()
          require("snacks").notifier.show_history()
        end,
        desc = "Notification History",
      },
      {
        "<leader>nd",
        function()
          require("snacks").notifier.hide()
        end,
        desc = "Dismiss All Notifications",
      },
    },
  },
}
