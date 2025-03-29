return {
  {
    "nvim-lualine/lualine.nvim",
    lazy = false,
    opts = {
      options = {
        refresh = {
          statusline = 1500,
          tabline = math.huge,
          winbar = math.huge,
        },
      },
      sections = {
        lualine_a = { "branch" },
        lualine_b = {},
        lualine_c = {},
        lualine_x = {},
        lualine_y = {
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
        lualine_z = {
          { "location", padding = { left = 0, right = 1 } },
        },
      },
      always_show_tabline = false,
    },
  },
}
