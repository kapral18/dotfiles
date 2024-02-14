local logo = [[


        _                             _     _                             ____
__   __(_) _ __ ___      __ _  _ __  (_)   | |  ___   __ _  _ __  _ __   / /\ \
\ \ / /| || '_ ` _ \    / _` || '_ \ | |   | | / _ \ / _` || '__|| '_ \ | |  | |
 \ V / | || | | | | | _| (_| || |_) || | _ | ||  __/| (_| || |   | | | || |  | |
  \_/  |_||_| |_| |_|(_)\__,_|| .__/ |_|(_)|_| \___| \__,_||_|   |_| |_|| |  | |
                              |_|                                       \_\/_/

                                                      [ @kapral18 ]
    ]]

return {
  "nvimdev/dashboard-nvim",
  opts = {
    config = {
      header = vim.split(logo, "\n"),
      center = {
        {
          action = "FzfLua files",
          desc = " Find file",
          icon = " ",
          key = "f",
        },
        {
          action = "ene | startinsert",
          desc = " New file",
          icon = " ",
          key = "n",
        },
        {
          action = "FzfLua oldfiles",
          desc = " Recent files",
          icon = " ",
          key = "r",
        },
        {
          action = "FzfLua live_grep_native",
          desc = " Find text",
          icon = " ",
          key = "g",
        },
        {
          action = function()
            require("fzf-lua").files({ cwd = vim.fn.stdpath("config") })
          end,
          desc = " Config",
          icon = " ",
          key = "c",
        },
        {
          action = 'lua require("persistence").load()',
          desc = " Restore Session",
          icon = " ",
          key = "s",
        },
        {
          action = "LazyExtras",
          desc = " Lazy Extras",
          icon = " ",
          key = "x",
        },
        {
          action = "Lazy",
          desc = " Lazy",
          icon = "󰒲 ",
          key = "l",
        },
        {
          action = "qa",
          desc = " Quit",
          icon = " ",
          key = "q",
        },
      },
    },
  },
}
