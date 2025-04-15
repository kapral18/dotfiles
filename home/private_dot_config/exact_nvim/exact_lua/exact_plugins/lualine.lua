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
        lualine_x = {},
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
  {
    "linrongbin16/lsp-progress.nvim",
    opts = {},
    lazy = false,
    dependencies = {
      {
        "nvim-lualine/lualine.nvim",
        config = function(_, opts)
          local new_opts = {
            sections = {
              lualine_x = {
                function()
                  -- invoke `progress` here.
                  return require("lsp-progress").progress()
                end,
              },
            },
          }
          opts = vim.tbl_deep_extend("force", opts, new_opts)
          require("lualine").setup(opts)

          -- listen lsp-progress event and refresh lualine
          vim.api.nvim_create_augroup("lualine_augroup", { clear = true })
          vim.api.nvim_create_autocmd("User", {
            group = "lualine_augroup",
            pattern = "LspProgressStatusUpdated",
            callback = require("lualine").refresh,
          })
        end,
      },
    },
  },
}
