return {
  {
    "nvim-treesitter/nvim-treesitter",
    opts = function(_, opts)
      opts.ensure_installed = opts.ensure_installed or {}
      if not vim.tbl_contains(opts.ensure_installed, "dockerfile") then
        table.insert(opts.ensure_installed, "dockerfile")
      end
    end,
  },
  {
    "mason-org/mason.nvim",
    opts = function(_, opts)
      opts.ensure_installed = opts.ensure_installed or {}
      for _, pkg in ipairs({ "dockerls", "docker-compose-language-service", "hadolint" }) do
        if not vim.tbl_contains(opts.ensure_installed, pkg) then
          table.insert(opts.ensure_installed, pkg)
        end
      end
    end,
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
