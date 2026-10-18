return {
  {
    "nvim-treesitter/nvim-treesitter",
    opts = function(_, opts)
      opts.ensure_installed = vim.list_extend(opts.ensure_installed or {}, { "yaml" })
      return opts
    end,
  },
  {
    "mason-org/mason.nvim",
    opts = function(_, opts)
      opts.ensure_installed = vim.list_extend(opts.ensure_installed or {}, { "actionlint" })
      return opts
    end,
  },
  -- Schema companion: auto-detect k8s schemas from apiVersion/kind, CRD support
  {
    "cenk1cenk2/schema-companion.nvim",
    version = false,
    dependencies = { "nvim-lua/plenary.nvim" },
    config = function()
      require("schema-companion").setup({
        log_level = vim.log.levels.WARN,
      })
    end,
  },
  {
    "neovim/nvim-lspconfig",
    dependencies = {
      { "b0o/SchemaStore.nvim", version = false },
      { "cenk1cenk2/schema-companion.nvim" },
    },
    opts = function(_, opts)
      -- Wrap yamlls config with schema-companion
      local sc = require("schema-companion")
      -- Let yamlls apply its own associations. Reapplying LSP matches through
      -- schema-companion replaces shared filename patterns with one buffer URI.
      local lsp_source = vim.tbl_extend("force", {}, sc.sources.lsp.setup(), { match = false })

      local adapter = sc.adapters.yamlls.setup({
        sources = {
          -- Auto-detect Kubernetes resources from apiVersion/kind
          sc.sources.matchers.kubernetes.setup({ version = "master" }),
          -- Allow selecting from LSP-provided schemas
          lsp_source,
        },
      })

      local yamlls_config = sc.setup_client(adapter, {
        -- Exclude helm filetype - helm_ls handles those
        filetypes = { "yaml", "yaml.docker-compose", "yaml.chezmoitmpl", "yaml.docker-compose.chezmoitmpl" },
        get_language_id = function(_, filetype)
          return filetype:match("^[^.]+")
        end,
        -- Prevent standalone yamlls from attaching to Helm charts (avoid diagnostic flicker)
        root_dir = function(bufnr, on_dir)
          -- If we find Chart.yaml, this is a Helm chart -> let helm_ls handle it
          if vim.fs.root(bufnr, "Chart.yaml") then
            return
          end
          -- Otherwise use standard root detection
          on_dir(vim.fs.root(bufnr, { ".git", "compose.yaml", "docker-compose.yaml" }))
        end,
        settings = {
          redhat = { telemetry = { enabled = false } },
          yaml = {
            keyOrdering = false,
            validate = true,
            schemaStore = { enable = false, url = "" },
            -- Custom tags for GitLab CI and other tools
            customTags = {
              "!reference sequence",
              "!include scalar",
              "!include_raw scalar",
            },
            schemas = vim.tbl_extend("force", require("schemastore").yaml.schemas(), {
              -- Kubernetes handled by schema-companion matchers
              kubernetes = "",
              -- GitHub
              ["https://www.schemastore.org/github-workflow.json"] = ".github/workflows/*.{yml,yaml}",
              ["https://www.schemastore.org/github-action.json"] = ".github/action.{yml,yaml}",
              ["https://www.schemastore.org/dependabot-2.0.json"] = ".github/dependabot.{yml,yaml}",
              -- GitLab
              ["https://gitlab.com/gitlab-org/gitlab/-/raw/master/app/assets/javascripts/editor/schema/ci.json"] = {
                ".gitlab-ci.yml",
                ".gitlab-ci.yaml",
                "*.gitlab-ci.yml",
                ".gitlab/**/*.{yml,yaml}",
              },
              -- Docker Compose
              ["https://raw.githubusercontent.com/compose-spec/compose-spec/master/schema/compose-spec.json"] = {
                "docker-compose*.{yml,yaml}",
                "compose*.{yml,yaml}",
              },
              -- Helm Chart.yaml (not templates)
              ["https://www.schemastore.org/chart.json"] = "Chart.{yml,yaml}",
              -- Ansible
              ["https://raw.githubusercontent.com/ansible/ansible-lint/main/src/ansiblelint/schemas/ansible.json#/$defs/playbook"] = {
                "**/playbooks/**/*.{yml,yaml}",
                "**/*playbook*.{yml,yaml}",
                "**/site.{yml,yaml}",
              },
              ["https://raw.githubusercontent.com/ansible/ansible-lint/main/src/ansiblelint/schemas/ansible.json#/$defs/tasks"] = {
                "**/tasks/**/*.{yml,yaml}",
                "**/handlers/**/*.{yml,yaml}",
              },
              -- Kustomization
              ["https://www.schemastore.org/kustomization.json"] = "kustomization.{yml,yaml}",
              -- Prettier
              ["https://www.schemastore.org/prettierrc.json"] = ".prettierrc.{yml,yaml}",
              -- Argo Workflows
              ["https://raw.githubusercontent.com/argoproj/argo-workflows/master/api/jsonschema/schema.json"] = {
                "**/workflows/**/*.{yml,yaml}",
                "**/*-workflow.{yml,yaml}",
              },
              -- Pre-commit
              ["https://www.schemastore.org/pre-commit-config.json"] = ".pre-commit-config.{yml,yaml}",
              -- Renovate
              ["https://docs.renovatebot.com/renovate-schema.json"] = {
                "renovate.json",
                ".renovaterc.json",
              },
            }),
          },
        },
      })

      opts.servers = opts.servers or {}
      opts.servers.yamlls = yamlls_config
      return opts
    end,
  },
  {
    "stevearc/conform.nvim",
    opts = function(_, opts)
      opts.formatters_by_ft = vim.tbl_deep_extend("force", opts.formatters_by_ft or {}, {
        yaml = { "prettierd", "prettier", stop_after_first = true },
      })
      return opts
    end,
  },
  -- Linting: actionlint for GitHub Actions (much better than schema validation alone)
  {
    "mfussenegger/nvim-lint",
    opts = function(_, opts)
      opts.linters_by_ft = vim.tbl_deep_extend("force", opts.linters_by_ft or {}, {
        -- actionlint only runs on GitHub workflow files (has built-in path detection)
        yaml = { "actionlint" },
      })

      -- Configure actionlint to only run on GitHub workflow files
      opts.linters = opts.linters or {}
      opts.linters.actionlint = {
        condition = function(ctx)
          return ctx.filename:match("%.github/workflows/") ~= nil
        end,
      }

      return opts
    end,
  },
}
