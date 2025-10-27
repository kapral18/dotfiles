return {
  {
    "stevearc/conform.nvim",
    dependencies = { "mason-org/mason.nvim" },
    lazy = false,
    cmd = "ConformInfo",
    keys = {
      {
        "<leader>cF",
        function()
          require("conform").format({ formatters = { "injected" }, timeout_ms = 3000 })
        end,
        mode = { "n", "x" },
        desc = "Format Injected Langs",
      },
    },
    opts = {
      notify_on_error = false,
      default_format_opts = {
        timeout_ms = 3000,
        async = false,
        quiet = false,
        lsp_format = "fallback",
      },
      formatters_by_ft = {
        lua = { "stylua" },
        fish = { "fish_indent" },
        go = { "goimports", "gofumpt" },
        sh = { "shfmt" },
        bash = { "shfmt" },
        python = { "isort", "black" },
        toml = { "taplo" },
        rust = { "rustfmt" },
        yaml = { "prettierd", "prettier" },
        json = { "prettierd", "prettier" },
        jsonc = { "prettierd", "prettier" },
        markdown = { "prettierd", "prettier" },
        mdx = { "prettierd", "prettier" },
        javascript = { "prettierd", "prettier" },
        javascriptreact = { "prettierd", "prettier" },
        typescript = { "prettierd", "prettier" },
        typescriptreact = { "prettierd", "prettier" },
        css = { "stylelint", "prettierd", "prettier" },
        scss = { "stylelint", "prettierd", "prettier" },
        jsonl = { "jsonl" },
        html = { "prettierd", "prettier" },
        vue = { "prettierd", "prettier" },
        graphql = { "prettierd", "prettier" },
      },
      formatters = {
        injected = { options = { ignore_errors = true } },
        jsonl = {
          command = "jq",
          args = { ".", "$FILENAME" },
        },
      },
    },
    config = function(_, opts)
      require("conform").setup(opts)

      -- Format on save via autocmd (not in opts)
      vim.api.nvim_create_autocmd("BufWritePre", {
        pattern = "*",
        callback = function(args)
          local disable_filetypes = { c = true, cpp = true }
          if disable_filetypes[vim.bo[args.buf].filetype] then
            return
          end
          require("conform").format({ bufnr = args.buf, timeout_ms = 3000, lsp_fallback = true })
        end,
      })
    end,
  },
  {
    "mason-org/mason.nvim",
    opts = function(_, opts)
      opts.ensure_installed = opts.ensure_installed or {}
      for _, pkg in ipairs({ "prettierd", "stylua", "shfmt" }) do
        if not vim.tbl_contains(opts.ensure_installed, pkg) then
          table.insert(opts.ensure_installed, pkg)
        end
      end
    end,
  },
}
