return {
  { import = "lazyvim.plugins.extras.coding.copilot" },
  { import = "lazyvim.plugins.extras.coding.copilot-chat" },
  {
    "dustinblackman/oatmeal.nvim",
    event = "VeryLazy",
    cmd = { "Oatmeal" },
    dependencies = {
      "folke/which-key.nvim",
    },
    opts = {
      backend = "ollama",
      model = "internlm2:latest",
    },
    config = function(_, opts)
      require("oatmeal").setup(opts)
      require("which-key").register({
        ["<leader>om"] = { "<cmd>Oatmeal<CR>", "[AI] Oatmeal: toggle", mode = { "n", "x" } },
      })
    end,
  },
  {
    "jonahgoldwastaken/copilot-status.nvim",
    event = "LspAttach",
    config = function()
      require("copilot_status").setup({
        icons = {
          idle = " ",
          error = " ",
          offline = " ",
          warning = " ",
          loading = " ",
        },
        debug = false,
      })
    end,
  },
  {
    "zbirenbaum/copilot.lua",
    event = "InsertEnter",
    opts = {
      filetypes = {
        ["*"] = function()
          local file_size = vim.fn.getfsize(vim.fn.expand("%"))
          if file_size > 100000 or file_size == -2 then
            return false
          end
          return true
        end,
        gitcommit = false,
        TelescopePrompt = false,
      },
      suggestion = {
        enabled = false,
        auto_trigger = false,
        keymap = {
          accept_word = false,
          accept_line = false,
        },
      },
      panel = {
        enabled = false,
      },
      server_opts_overrides = {
        trace = "verbose",
        settings = {
          advanced = {
            listCount = 3,
            inlineSuggestCount = 3,
          },
        },
      },
    },
  },
}
