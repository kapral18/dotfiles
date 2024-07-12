return {
  { import = "lazyvim.plugins.extras.coding.copilot", enabled = false },
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
      require("which-key").add({
        { "<leader>om", "<cmd>Oatmeal<CR>", desc = "[AI] Oatmeal: toggle", mode = { "n", "x" } },
      })
    end,
  },
  {
    "zbirenbaum/copilot.lua",
    event = "InsertEnter",
    enabled = false,
    opts = function()
      vim.api.nvim_set_hl(0, "CopilotSuggestion", { fg = "#83a598" })
      vim.api.nvim_set_hl(0, "CopilotAnnotation", { fg = "#03a598" })
      return {
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
      }
    end,
  },
  {
    "github/copilot.vim",
    lazy = false,
    init = function()
      vim.api.nvim_set_hl(0, "CopilotSuggestion", { fg = "#83a598" })
      vim.api.nvim_set_hl(0, "CopilotAnnotation", { fg = "#03a598" })
    end,
  },
}
