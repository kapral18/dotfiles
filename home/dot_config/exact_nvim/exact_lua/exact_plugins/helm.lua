-- K8s Schema Lookup (modularized in k8s_schema.lua)
local K8sSchema = require("util.k8s")

vim.api.nvim_create_autocmd("FileType", {
  pattern = "helm",
  callback = function()
    vim.keymap.set("n", "gK", K8sSchema.show_property, { buffer = true, desc = "Kubernetes JSON schema" })
  end,
})

return {
  {
    "nvim-treesitter/nvim-treesitter",
    opts = function(_, opts)
      opts.ensure_installed = vim.list_extend(opts.ensure_installed or {}, { "helm" })
      return opts
    end,
  },
  {
    "mason-org/mason.nvim",
    opts = function(_, opts)
      opts.ensure_installed = vim.list_extend(opts.ensure_installed or {}, { "helm-ls" })
      return opts
    end,
  },
  {
    "neovim/nvim-lspconfig",
    dependencies = {
      { "cenk1cenk2/schema-companion.nvim" },
    },
    opts = function(_, opts)
      -- Wrap helm_ls config with schema-companion for k8s schema detection
      local sc = require("schema-companion")
      local helm_ls_config = sc.setup_client(
        sc.adapters.helmls.setup({
          sources = {
            -- Disabled auto-detection to prevent strict K8s validation errors on templates
          },
        }),
        {
          settings = {
            ["helm-ls"] = {
              logLevel = "info",
              valuesFiles = {
                mainValuesFile = "values.yaml",
                lintOverlayValuesFile = "values.lint.yaml",
                additionalValuesFilesGlobPattern = "values*.yaml",
              },
              helmLint = {
                enabled = true,
                ignoredMessages = {},
              },
              yamlls = {
                enabled = true,
                enabledForFilesGlob = "*.{yaml,yml}",
                diagnosticsLimit = 50,
                showDiagnosticsDirectly = false,
                path = "yaml-language-server",
                config = {
                  schemas = {
                    -- kubernetes = "templates/**", -- Disabled to prevent strict K8s validation on templates
                  },
                  completion = true,
                  hover = true,
                },
              },
            },
          },
          -- Custom handler removed as requested (relying on native helm_ls support)
        }
      )

      opts.servers = opts.servers or {}
      opts.servers.helm_ls = helm_ls_config
      return opts
    end,
  },
  {
    "stevearc/conform.nvim",
    opts = function(_, opts)
      opts.formatters_by_ft = vim.tbl_deep_extend("force", opts.formatters_by_ft or {}, {
        helm = { "prettier", stop_after_first = true },
      })
      return opts
    end,
  },
}

