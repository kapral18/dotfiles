local util = require("util")

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

  { "folke/snacks.nvim", opts = { dashboard = { enabled = false } } },
  {
    "nvimdev/dashboard-nvim",
    lazy = false,
    event = "VimEnter",
    opts = function()
      logo = string.rep("\n", 8) .. logo .. "\n\n"

      local opts = {
        theme = "doom",
        hide = {
          -- this is taken care of by lualine
          -- enabling this messes up the actual laststatus setting after loading a file
          statusline = false,
        },
        config = {
          header = vim.split(logo, "\n"),
          -- stylua: ignore
          center = {
            { action = util.pick("files"),                               desc = " Find File",       icon = " ", key = "f" },
            { action = "ene | startinsert",                              desc = " New File",        icon = " ", key = "n" },
            { action = util.pick("files", { cwd = vim.fn.stdpath("config") }), desc = " Config",          icon = " ", key = "c" },
            { action = "Lazy",                                           desc = " Lazy",            icon = "󰒲 ", key = "l" },
            { action = function() vim.api.nvim_input("<cmd>qa<cr>") end, desc = " Quit",            icon = " ", key = "q" },
          },
          footer = function()
            local stats = require("lazy").stats()
            local ms = (math.floor(stats.startuptime * 100 + 0.5) / 100)
            return { "⚡ Neovim loaded " .. stats.loaded .. "/" .. stats.count .. " plugins in " .. ms .. "ms" }
          end,
        },
      }

      for _, button in ipairs(opts.config.center) do
        button.desc = button.desc .. string.rep(" ", 43 - #button.desc)
        button.key_format = "  %s"
      end

      -- open dashboard after closing lazy
      if vim.o.filetype == "lazy" then
        vim.api.nvim_create_autocmd("WinClosed", {
          pattern = tostring(vim.api.nvim_get_current_win()),
          once = true,
          callback = function()
            vim.schedule(function()
              vim.api.nvim_exec_autocmds("UIEnter", { group = "dashboard" })
            end)
          end,
        })
      end

      return opts
    end,
  },
}
