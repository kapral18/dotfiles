return {
  {
    "williamboman/mason.nvim",
    opts = function(_, opts)
      opts.ensure_installed = opts.ensure_installed or {}
      vim.list_extend(opts.ensure_installed, { "gh" })
    end,
  },
  {
    "almo7aya/openingh.nvim",
    cmd = { "OpenInGHRepo", "OpenInGHFile", "OpenInGHFileLines" },
    keys = {
      { "<leader>grr", "<cmd>OpenInGHRepo<CR>", desc = "Open git repo in web", mode = { "n" } },
      { "<leader>grf", "<cmd>OpenInGHFile<CR>", desc = "Open git file in web", mode = { "n" } },
      { "<leader>grl", "<cmd>OpenInGHFileLines<CR>", desc = "Open current line in web", mode = { "n", "x", "v" } },
    },
  },
  {
    "ldelossa/gh.nvim",
    dependencies = {
      {
        "ldelossa/litee.nvim",
        config = function()
          require("litee.lib").setup()
        end,
      },
    },
    config = function()
      require("litee.gh").setup()

      local wk = require("which-key")
      wk.add({
        { "<leader>gp", group = "Pull Request" },

        { "<leader>gpc", group = "Commit" },
        { "<leader>gpcc", "<cmd>GHCloseCommit<cr>", desc = "Close" },
        { "<leader>gpce", "<cmd>GHExpandCommit<cr>", desc = "Expand" },
        { "<leader>gpco", "<cmd>GHOpenToCommit<cr>", desc = "Open To" },
        { "<leader>gpcp", "<cmd>GHPopOutCommit<cr>", desc = "Pop Out" },
        { "<leader>gpcz", "<cmd>GHCollapseCommit<cr>", desc = "Collapse" },

        { "<leader>gpi", group = "Issues" },
        { "<leader>gpip", "<cmd>GHPreviewIssue<cr>", desc = "Preview" },

        { "<leader>gpl", group = "Litee" },
        { "<leader>gplt", "<cmd>LTPanel<cr>", desc = "Toggle Panel" },

        { "<leader>gpr", group = "Review" },
        { "<leader>gprb", "<cmd>GHStartReview<cr>", desc = "Begin" },
        { "<leader>gprc", "<cmd>GHCloseReview<cr>", desc = "Close" },
        { "<leader>gprd", "<cmd>GHDeleteReview<cr>", desc = "Delete" },
        { "<leader>gpre", "<cmd>GHExpandReview<cr>", desc = "Expand" },
        { "<leader>gprs", "<cmd>GHSubmitReview<cr>", desc = "Submit" },
        { "<leader>gprz", "<cmd>GHCollapseReview<cr>", desc = "Collapse" },

        { "<leader>gpp", group = "Pull Request" },
        { "<leader>gppc", "<cmd>GHClosePR<cr>", desc = "Close" },
        { "<leader>gppd", "<cmd>GHPRDetails<cr>", desc = "Details" },
        { "<leader>gppe", "<cmd>GHExpandPR<cr>", desc = "Expand" },
        { "<leader>gppo", "<cmd>GHOpenPR<cr>", desc = "Open" },
        { "<leader>gppp", "<cmd>GHPopOutPR<cr>", desc = "PopOut" },
        { "<leader>gppr", "<cmd>GHRefreshPR<cr>", desc = "Refresh" },
        { "<leader>gppt", "<cmd>GHOpenToPR<cr>", desc = "Open To" },
        { "<leader>gppz", "<cmd>GHCollapsePR<cr>", desc = "Collapse" },

        { "<leader>gpt", group = "Threads" },
        { "<leader>gptc", "<cmd>GHCreateThread<cr>", desc = "Create" },
        { "<leader>gptn", "<cmd>GHNextThread<cr>", desc = "Next" },
        { "<leader>gptt", "<cmd>GHToggleThread<cr>", desc = "Toggle" },
      })
    end,
  },
}
