return {
  {
    "Xuyuanp/scrollbar.nvim",
    lazy = false,
    init = function()
      local group_id = vim.api.nvim_create_augroup("scrollbar_init", { clear = true })
      vim.g.excluded_filetypes = {
        "NvimTree",
        "TelescopePrompt",
        "alpha",
        "commit",
        "dap-repl",
        "dapui_breakpoints",
        "dapui_console",
        "dapui_scopes",
        "dapui_stacks",
        "dapui_watches",
        "dashboard",
        "fugitive",
        "fugitiveblame",
        "fzf",
        "git",
        "gitcommit",
        "grug-far",
        "lir",
        "neo-tree",
        "noice",
        "packer",
        "prompt",
        "startify",
        "telescope",
      }

      vim.g.scrollbar_width = 1
      vim.g.scrollbar_highlight = {
        head = "Normal",
        body = "Normal",
        tail = "Normal",
      }
      vim.g.scrollbar_shape = {
        head = "▲",
        body = "|",
        tail = "▼",
      }

      vim.g.scrollbar_right_offset = 0
      vim.g.scrollbar_min_size = 3
      vim.g.scrollbar_max_size = 7

      vim.api.nvim_create_autocmd({ "BufEnter", "WinScrolled", "WinResized" }, {
        group = group_id,
        desc = "Show or refresh scrollbar",
        pattern = { "*" },
        callback = function()
          require("scrollbar").show()
        end,
      })
    end,
  },
}
