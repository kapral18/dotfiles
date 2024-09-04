return {
  {
    "folke/noice.nvim",
    event = "VeryLazy",
    opts = {
      presets = {
        bottom_search = true, -- use a classic bottom cmdline for search
        command_palette = true, -- position the cmdline and popupmenu together
        long_message_to_split = true, -- long messages will be sent to a split
        inc_rename = true, -- enables an input dialog for inc-rename.nvim
        lsp_doc_border = false, -- add a border to hover docs and signature help
        cmdline_output_to_split = true, -- send the output of a command you executed in the cmdline to a split
      },
      cmdline = {
        enabled = true,
        view = "cmdline_popup",
        format = {
          cmdline = false,
          search_down = false,
          search_up = false,
          filter = false,
          lua = false,
          help = false,
        },
      },
      popupmenu = {
        enabled = true, -- enables the Noice popupmenu UI
        backend = "nui", -- backend to use to show regular cmdline completions
      },
      lsp = {
        progress = {
          enabled = true,
        },
        signature = {
          enabled = true,
          auto_open = {
            enabled = true,
            trigger = true,
            luasnip = true,
            throttle = 50,
          },
          view = nil, -- when nil, use defaults from documentation
          opts = {
            focusable = false,
            size = {
              max_height = 15,
              max_width = 60,
            },
            win_options = {
              wrap = false,
            },
          },
        },
        hover = {
          silent = true,
        },
        documentation = {
          opts = {
            border = {
              padding = { 0, 0 },
            },
          },
        },
        override = {
          -- override the default lsp markdown formatter with Noice
          ["vim.lsp.util.convert_input_to_markdown_lines"] = true,
          -- override the lsp markdown formatter with Noice
          ["vim.lsp.util.stylize_markdown"] = true,
          -- override cmp documentation with Noice (needs the other options to work)
          ["cmp.entry.get_documentation"] = true,
        },
      },
      views = {
        cmdline_popup = {
          position = {
            row = 3,
            col = "50%",
          },
          size = {
            width = 60,
            height = "auto",
          },
        },
        popupmenu = {
          relative = "editor",
          position = {
            row = 8,
            col = "50%",
          },
          size = {
            width = 60,
            height = 10,
          },
          border = {
            style = "rounded",
            padding = { 0, 1 },
          },
          win_options = {
            winhighlight = { Normal = "Normal", FloatBorder = "DiagnosticInfo" },
          },
        },
        mini = {
          zindex = 100,
          win_options = { winblend = 0 },
        },
      },
    },
    config = function(_, opts)
      require("noice").setup(opts)
      vim.lsp.handlers["textDocument/hover"] = require("noice").hover
      vim.lsp.handlers["textDocument/signatureHelp"] = require("noice").signature
    end,
  },
}
