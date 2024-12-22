return {
  {
    "David-Kunz/gen.nvim",
    opts = {
      model = "qwen2.5-coder:32b", -- The model to use. Can be "gpt-3" or "gpt-4" or "gpt-j
      quit_map = "q", -- set keymap to close the response window
      retry_map = "<c-r>", -- set keymap to re-send the current prompt
      accept_map = "<c-cr>", -- set keymap to replace the previous selection with the last result
      display_mode = "split", -- The display mode. Can be "float" or "split" or "horizontal-split".
      show_prompt = false, -- Shows the prompt submitted to Ollama.
      show_model = true,
    },
    keys = {
      { "<leader>om", ":Gen<CR>", mode = { "n", "x" }, desc = "Generate code" },
    },
  },
  {
    "github/copilot.vim",
    lazy = false,
    init = function()
      vim.api.nvim_set_hl(0, "CopilotSuggestion", { fg = "#83a598" })
      vim.api.nvim_set_hl(0, "CopilotAnnotation", { fg = "#03a598" })
    end,
  },
  {
    "CopilotC-Nvim/CopilotChat.nvim",
    lazy = false,
    opts = {
      model = "claude-3.5-sonnet",
    },
  },
}
