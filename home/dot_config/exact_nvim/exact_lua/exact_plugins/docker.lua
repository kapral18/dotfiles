return {
  {
    "nvim-treesitter/nvim-treesitter",
    opts = function(_, opts)
      opts.ensure_installed = vim.list_extend(opts.ensure_installed or {}, { "dockerfile" })
      return opts
    end,
  },
  {
    "mason-org/mason.nvim",
    opts = function(_, opts)
      opts.ensure_installed = vim.list_extend(opts.ensure_installed or {}, { "hadolint" })
      return opts
    end,
  },
  {
    "neovim/nvim-lspconfig",
    opts = {
      servers = {
        dockerls = {
          filetypes = { "dockerfile" },
        },
        docker_compose_language_service = {
          filetypes = { "yaml", "yaml.docker-compose" },
        },
      },
    },
  },
  {
    "mfussenegger/nvim-lint",
    opts = function(_, opts)
      opts.linters_by_ft = vim.tbl_deep_extend("force", opts.linters_by_ft or {}, {
        dockerfile = { "hadolint" },
      })
      return opts
    end,
  },
}
