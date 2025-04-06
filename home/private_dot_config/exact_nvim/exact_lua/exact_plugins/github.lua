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
      { "<leader>gor", "<cmd>OpenInGHRepo<CR>", desc = "Open git repo in web", mode = { "n" } },
      { "<leader>gof", "<cmd>OpenInGHFile<CR>", desc = "Open git file in web", mode = { "n" } },
      { "<leader>gol", "<cmd>OpenInGHFileLines<CR>", desc = "Open current line in web", mode = { "n", "x", "v" } },
    },
  },
  {
    "pwntester/octo.nvim",
    cmd = "Octo",
    dependencies = {
      "nvim-lua/plenary.nvim",
      "nvim-telescope/telescope.nvim",
      "nvim-tree/nvim-web-devicons",
    },
    event = { { event = "BufReadCmd", pattern = "octo://*" } },
    opts = {
      use_local_fs = true,
      enable_builtin = true,
      default_to_projects_v2 = true,
      default_merge_method = "squash",
      timeout = 55000,
      issues = {
        order_by = {
          field = "COMMENTS",
          direction = "DESC",
        },
      },
    },
    keys = {
      { "<leader>go", "", desc = "+octo" },
      { "<leader>goa", "<CMD>Octo actions<CR>", desc = "List Actions (Octo)" },
      { "<leader>gop", "", desc = "PR Actions (Octo)" },
      { "<leader>gops", "<CMD>Octo pr search<CR>", desc = "Search PR (Octo)" },
      { "<leader>goi", "", desc = "Issue Actions (Octo)" },
      { "<leader>gois", "<CMD>Octo issue search<CR>", desc = "Search Issues (Octo)" },

      { "<localleader>a", "", desc = "+assignee (Octo)", ft = "octo" },
      { "<localleader>c", "", desc = "+comment/code (Octo)", ft = "octo" },
      { "<localleader>l", "", desc = "+label (Octo)", ft = "octo" },
      { "<localleader>i", "", desc = "+issue (Octo)", ft = "octo" },
      { "<localleader>r", "", desc = "+react (Octo)", ft = "octo" },
      { "<localleader>p", "", desc = "+pr (Octo)", ft = "octo" },
      { "<localleader>pr", "", desc = "+rebase (Octo)", ft = "octo" },
      { "<localleader>ps", "", desc = "+squash (Octo)", ft = "octo" },
      { "<localleader>v", "", desc = "+review (Octo)", ft = "octo" },
      { "<localleader>g", "", desc = "+goto_issue (Octo)", ft = "octo" },

      { "@", "@<C-x><C-o>", mode = "i", ft = "octo", silent = true },
      { "#", "#<C-x><C-o>", mode = "i", ft = "octo", silent = true },
    },
  },
}
