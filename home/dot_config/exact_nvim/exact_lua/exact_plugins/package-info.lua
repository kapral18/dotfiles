return {
  {
    "vuki656/package-info.nvim",
    event = {
      "BufRead package.json",
    },
    opts = {
      hide_up_to_date = true,
      hide_unstable_versions = true,
    },
    -- stylua: ignore
    keys = {
      { "<leader>ps", "<cmd>lua require('package-info').toggle()<cr>", desc = "Toglge Package Versions" },
      { "<leader>pu", "<cmd>lua require('package-info').update()<cr>", desc = "Update Package" },
      { "<leader>pr", "<cmd>lua require('package-info').delete()<cr>", desc = "Remove Package" },
      { "<leader>pv", "<cmd>lua require('package-info').change_version()<cr>", desc = "Change Package Version" },
      { "<leader>pn", "<cmd>lua require('package-info').install()<cr>", desc = "Install New Dependency" },
    },
  },
  {
    "folke/which-key.nvim",
    opts = {
      defaults = {
        ["<leader>p"] = { name = " packages" },
      },
    },
  },
}
