return {
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
      model = "DeepSeek-V3-0324",
    },
  },
}
