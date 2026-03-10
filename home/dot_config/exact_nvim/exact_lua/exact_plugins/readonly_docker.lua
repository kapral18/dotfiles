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
          -- Only attach to docker-compose files, not all yaml
          filetypes = { "yaml.docker-compose" },
          root_dir = function(fname)
            -- Only activate for docker-compose files
            local basename = vim.fn.fnamemodify(fname, ":t")
            if
              basename:match("^docker%-compose")
              or basename:match("^compose")
              or basename == "docker-compose.yaml"
              or basename == "docker-compose.yml"
              or basename == "compose.yaml"
              or basename == "compose.yml"
            then
              return vim.fn.fnamemodify(fname, ":h")
            end
            return nil
          end,
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
