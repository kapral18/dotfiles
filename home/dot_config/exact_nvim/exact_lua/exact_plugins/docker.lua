return {
  {
    "nvim-treesitter/nvim-treesitter",
    opts = {
      ensure_installed = { "dockerfile" },
    },
  },
  {
    "mason-org/mason.nvim",
    opts = {
      ensure_installed = { "dockerls", "docker-compose-language-service", "hadolint" },
    },
  },
  {
    "neovim/nvim-lspconfig",
    opts = function(_, opts)
      opts.servers = opts.servers or {}
      opts.servers.dockerls = vim.tbl_deep_extend("force", {
        filetypes = { "dockerfile" },
      }, opts.servers.dockerls or {})
      opts.servers.docker_compose_language_service = vim.tbl_deep_extend("force", {
        filetypes = { "yaml", "yaml.docker-compose" },
      }, opts.servers.docker_compose_language_service or {})
    end,
  },
  {
    "mfussenegger/nvim-lint",
    opts = function(_, opts)
      opts.linters_by_ft = opts.linters_by_ft or {}
      opts.linters_by_ft.dockerfile = opts.linters_by_ft.dockerfile or { "hadolint" }
    end,
  },
}
