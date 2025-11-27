return {
  {
    "folke/snacks.nvim",
    opts = {
      dashboard = {
        enabled = true,
        preset = {
          -- stylua: ignore
          ---@type snacks.dashboard.Item[]
          keys = {
            { icon = " ", key = "f", desc = "Find File", action = ":lua require('util.pick')('files')" },
            { icon = " ", key = "n", desc = "New File", action = ":ene | startinsert" },
            { icon = " ", key = "c", desc = "Config", action = ":lua require('util.pick').config_files()" },
            { icon = "󰒲 ", key = "l", desc = "Lazy", action = ":Lazy" },
            { icon = " ", key = "q", desc = "Quit", action = ":qa" },
          },
        },
        sections = {
          { section = "header" },
          { section = "keys", gap = 1, padding = 1 },
          { section = "startup" },
        },
      },
      bigfile = { enabled = false },
      indent = { enabled = false },
      input = { enabled = false },
      notifier = { enabled = true },
      picker = {
        enabled = true,
      },
      profiler = { enabled = true },
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
    config = function(_, opts)
      local Snacks = require("snacks")
      Snacks.setup(opts)

      local util = require("util")

      -- Toggle mappings
      Snacks.toggle.option("spell", { name = "Spelling" }):map("<leader>us")
      Snacks.toggle.option("wrap", { name = "Wrap" }):map("<leader>uw")
      Snacks.toggle.option("relativenumber", { name = "Relative Number" }):map("<leader>uL")
      Snacks.toggle.diagnostics():map("<leader>ud")
      Snacks.toggle.line_number():map("<leader>ul")
      Snacks.toggle
        .option("conceallevel", { off = 0, on = vim.o.conceallevel > 0 and vim.o.conceallevel or 2, name = "Conceal Level" })
        :map("<leader>uc")
      Snacks.toggle
        .option("showtabline", { off = 0, on = vim.o.showtabline > 0 and vim.o.showtabline or 2, name = "Tabline" })
        :map("<leader>uA")
      Snacks.toggle.treesitter():map("<leader>uT")
      Snacks.toggle.option("background", { off = "light", on = "dark", name = "Dark Background" }):map("<leader>ub")
      Snacks.toggle.dim():map("<leader>uD")
      Snacks.toggle.animate():map("<leader>ua")
      Snacks.toggle.indent():map("<leader>ug")
      Snacks.toggle.profiler():map("<leader>dpp")
      Snacks.toggle.profiler_highlights():map("<leader>dph")
      Snacks.toggle.inlay_hints():map("<leader>uh")
      Snacks.toggle.zoom():map("<leader>wm"):map("<leader>uZ")
      Snacks.toggle.zen():map("<leader>uz")
      util.format.snacks_toggle():map("<leader>uf")
      util.format.snacks_toggle(true):map("<leader>uF")
    end,
    keys = {
      -- Notifier
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
      -- Profiler
      {
        "<leader>dps",
        function()
          require("snacks").profiler.scratch()
        end,
        desc = "Profiler Scratch Buffer",
      },
      -- Lazygit
      {
        "<leader>gg",
        function()
          require("snacks").lazygit({ cwd = require("util").root.git() })
        end,
        desc = "Lazygit (Root Dir)",
      },
      {
        "<leader>gG",
        function()
          require("snacks").lazygit()
        end,
        desc = "Lazygit (cwd)",
      },
      -- Git pickers
      {
        "<leader>gL",
        function()
          require("snacks").picker.git_log()
        end,
        desc = "Git Log (cwd)",
      },
      {
        "<leader>gB",
        function()
          require("snacks").picker.git_log_line()
        end,
        desc = "Git Blame Line",
      },
      {
        "<leader>gf",
        function()
          require("snacks").picker.git_log_file()
        end,
        desc = "Git Current File History",
      },
      {
        "<leader>gl",
        function()
          require("snacks").picker.git_log({ cwd = require("util").root.git() })
        end,
        desc = "Git Log (Root Dir)",
      },
      -- Gitbrowse
      {
        "<leader>go",
        function()
          require("snacks").gitbrowse()
        end,
        desc = "Git Browse (open)",
        mode = { "n", "x" },
      },
      {
        "<leader>gO",
        function()
          require("snacks").gitbrowse({
            open = function(url)
              vim.fn.setreg("+", url)
            end,
            notify = false,
          })
        end,
        desc = "Git Browse (copy)",
        mode = { "n", "x" },
      },
      -- Bufdelete
      {
        "<leader>bd",
        function()
          require("snacks").bufdelete()
        end,
        desc = "Delete Buffer",
      },
      {
        "<leader>bo",
        function()
          require("snacks").bufdelete.other()
        end,
        desc = "Delete Other Buffers",
      },
      -- Terminal
      {
        "<leader>fT",
        function()
          require("snacks").terminal()
        end,
        desc = "Terminal (cwd)",
      },
      {
        "<leader>ft",
        function()
          require("snacks").terminal(nil, { cwd = require("util").root.get() })
        end,
        desc = "Terminal (Root Dir)",
      },
      {
        "<c-/>",
        function()
          require("snacks").terminal(nil, { cwd = require("util").root.get() })
        end,
        desc = "Terminal (Root Dir)",
        mode = { "n", "t" },
      },
      {
        "<c-_>",
        function()
          require("snacks").terminal(nil, { cwd = require("util").root.get() })
        end,
        desc = "which_key_ignore",
        mode = { "n", "t" },
      },
    },
  },
}
