return {
  {
    "nvim-lualine/lualine.nvim",
    lazy = false,
    opts = {
      options = {
        refresh = {
          tabline = math.huge,
          winbar = math.huge,
        },
      },
      sections = {
        lualine_a = { "branch" },
        lualine_b = {},
        lualine_c = {},
        lualine_x = {
          -- { "progress", separator = " ", padding = { left = 1, right = 0 } },
          {
            "lsp_status",
            icon = "", -- f013
            symbols = {
              -- Standard unicode symbols to cycle through for LSP progress:
              spinner = { "⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏" },
              -- Standard unicode symbol for when LSP is done:
              done = "✓",
              -- Delimiter inserted between LSP names:
              separator = " ",
            },
            -- List of LSP names to ignore (e.g., `null-ls`):
            ignore_lsp = {},
          },
        },
        lualine_y = {
          {
            function()
              local current_line = vim.fn.line(".")
              local total_lines = vim.fn.line("$")
              local width = 10

              if total_lines <= 1 then
                return string.rep("▁", width)
              end

              local progress = (current_line - 1) / (total_lines - 1)
              local filled = math.floor(progress * width + 0.5)

              local bar = string.rep("█", filled) .. string.rep("▁", width - filled)
              return bar
            end,
            color = { fg = "#5e81ac" }, -- light blue
            separator = "",
          },
        },
        lualine_z = {
          { "location", padding = { left = 0, right = 1 } },
        },
      },
      always_show_tabline = false,
    },
  },
}
