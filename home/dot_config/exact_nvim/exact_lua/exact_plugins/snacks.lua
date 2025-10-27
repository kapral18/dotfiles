return {
  {
    "folke/snacks.nvim",
    opts = {
      bigfile = { enabled = false },
      indent = { enabled = false },
      input = { enabled = false },
      notifier = { enabled = true },
      picker = {
        enabled = true,
      },
      scope = { enabled = false },
      scroll = { enabled = false },
      statuscolumn = { enabled = false }, -- managed manually in options.lua
      toggle = { enabled = true },
      words = { enabled = false },
      quickfile = { enabled = false },
      scratch = {
        enabled = true,
        win = {
          width = 0.8,
          height = 0.8,
        },
      },
    },
    keys = {
      { "<leader>n",  false },
      { "<leader>un", false },
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
