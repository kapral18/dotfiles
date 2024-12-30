return {
  {
    "dyng/ctrlsf.vim",
    lazy = false,
    keys = {
      { "<leader>sfw", "<Plug>CtrlSFCwordPath", desc = "S&R Word Under Cursor" },
      { "<leader>sfb", "<Plug>CtrlSFCCwordPath", desc = "S&R Word Under Cursor (With Boundaries)" },
      { "<leader>sfl", "<Plug>CtrlSFPwordPath", desc = "S&R Last Search Path" },
      { "<leader>sfv", "<Plug>CtrlSFVwordPath", desc = "S&R Word Under Cursor", mode = "x" },
    },
    init = function()
      vim.g.ctrlsf_backend = "rg"
      vim.g.ctrlsf_extra_backend_args = {
        rg = "--hidden",
      }
      vim.g.ctrlsf_parse_speed = 250
      vim.g.ctrlsf_auto_focus = {
        at = "start",
      }
      vim.g.ctrlsf_fold_result = 1
      vim.g.ctrlsf_populate_qflist = 1
      vim.g.ctrlsf_regex_pattern = 1
      vim.g.ctrlsf_default_view_mode = "normal"
      vim.g.ctrlsf_auto_preview = 1
      vim.g.ctrlsf_search_mode = "async"
      vim.g.ctrlsf_ignore_dir =
        { "bower_components", "node_modules", "dist", "build", ".git", ".idea", "reports", ".nyc_output" }
      vim.g.ctrlsf_extra_root_markers = { ".git", "package.json", "yarn.lock", "package-lock.json" }
      vim.g.ctrlsf_position = "bottom"
      vim.g.ctrlsf_context = "-C 0"
      vim.g.ctrlsf_mapping = {
        open = { "<CR>", "o" },
        openb = "O",
        split = "<C-O>",
        vsplit = "",
        tab = "t",
        tabb = "T",
        popen = "p",
        popenf = "P",
        quit = "q",
        next = "<C-J>",
        prev = "<C-K>",
        nfile = "n",
        pfile = "N",
        pquit = "q",
        loclist = "",
        chgmode = "M",
        stop = "<C-C>",
      }
    end,
  },
  {
    "cshuaimin/ssr.nvim",
    keys = {
      {
        "<leader>sx",
        function()
          require("ssr").open()
        end,
        desc = "Search & Replace",
        mode = { "n", "x" },
      },
    },
    opts = {
      border = "rounded",
      min_width = 50,
      min_height = 5,
      max_width = 120,
      max_height = 25,
      adjust_window = true,
      keymaps = {
        close = "q",
        next_match = "n",
        prev_match = "N",
        replace_confirm = "<cr>",
        replace_all = "<leader><cr>",
      },
    },
  },
}
