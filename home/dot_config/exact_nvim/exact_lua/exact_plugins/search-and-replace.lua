return {
  {
    "nvim-pack/nvim-spectre",
    enabled = false,
  },
  {
    "dyng/ctrlsf.vim",
    enabled = false,
    keys = {
      { "<leader>srr", "<Plug>CtrlSFCwordPath", desc = "S&R Word Under Cursor" },
      { "<leader>srb", "<Plug>CtrlSFCCwordPath", desc = "S&R Word Under Cursor (With Boundaries)" },
      { "<leader>srl", "<Plug>CtrlSFPwordPath", desc = "S&R Last Search Path" },
      { "<leader>srr", "<Plug>CtrlSFVwordPath", desc = "S&R Word Under Cursor", mode = "x" },
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
    "MagicDuck/grug-far.nvim",
    event = "VeryLazy",
    opts = function()
      vim.api.nvim_create_autocmd("FileType", {
        group = vim.api.nvim_create_augroup("extra-grug-far-keybinds", { clear = true }),
        pattern = { "grug-far" },
        callback = function()
          vim.keymap.set("n", "<localleader>w", function()
            require("grug-far").toggle_flags({ "--fixed-strings" })
          end, { buffer = true })
          vim.keymap.set("n", "<localleader>i", function()
            require("grug-far").toggle_flags({ "--no-ignore" })
          end, { buffer = true })
          vim.keymap.set("n", "<localleader>h", function()
            require("grug-far").toggle_flags({ "--hidden" })
          end, { buffer = true })
        end,
      })

      return { headerMaxWidth = 80 }
    end,
    keys = {
      {
        "<leader>sr",
        function()
          require("grug-far").grug_far({ prefills = { search = vim.fn.expand("<cword>") } })
        end,
        desc = "Search & Replace Word Under Cursor",
      },
      {
        "<leader>sr",
        function()
          local is_visual = vim.fn.mode():lower():find("v")
          if is_visual then
            vim.cmd([[normal! v]])
          end
          require("grug-far").with_visual_selection()
        end,

        desc = "Search & Replace Visual Selection",
        mode = "x",
      },
    },
  },
}
