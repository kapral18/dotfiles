return {
  {
    "rcarriga/nvim-notify",
    opts = {
      fps = 15,
      stages = "static",
      render = "minimal",
      timeout = 2500,
    },
    config = function(_, opts)
      local notify = require("notify")
      notify.setup(opts)
      vim.notify = notify
    end,
  },
}
