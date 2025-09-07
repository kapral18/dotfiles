return {
  {
    "williamboman/mason.nvim",
    opts = function(_, opts)
      vim.list_extend(opts.ensure_installed, {
        "proselint",
      })
    end,
  },
  {
    "mfussenegger/nvim-lint",
    opts = function(_, opts)
      -- Preserve your original linters_by_ft configuration
      opts.linters_by_ft = opts.linters_by_ft or {}
      opts.linters_by_ft.markdown = { "proselint" }
      opts.linters_by_ft.python = { "ruff" } -- Keep your ruff configuration

      -- Override proselint linter with condition to exclude temp files
      opts.linters = opts.linters or {}
      opts.linters.proselint = {
        condition = function(ctx)
          local filepath = ctx.filename or ""
          -- Skip linting for temporary files
          if filepath:match("^/private/var/folders/") or filepath:match("^/tmp/") or filepath == "" then
            return false
          end
          return true
        end,
      }

      return opts
    end,
  },
}
