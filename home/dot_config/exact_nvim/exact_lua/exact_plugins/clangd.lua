return {
  {
    "nvim-treesitter/nvim-treesitter",
    opts = function(_, opts)
      opts.ensure_installed = vim.list_extend(opts.ensure_installed or {}, { "c", "cpp", "cuda" })
      return opts
    end,
  },
  {
    "mason-org/mason.nvim",
    opts = function(_, opts)
      opts.ensure_installed = vim.list_extend(opts.ensure_installed or {}, { "clang-format", "codelldb" })
      return opts
    end,
  },
  {
    "p00f/clangd_extensions.nvim",
    lazy = true,
    opts = {
      inlay_hints = {
        inline = false,
      },
      ast = {
        role_icons = {
          type = "󰜁",
          declaration = "󰙠",
          expression = "󰫈",
          statement = ";",
          specifier = "󰪥",
          ["template argument"] = "󰫈",
        },
        kind_icons = {
          Compound = "󰪥",
          Recovery = "",
          TranslationUnit = "󰉿",
          PackExpansion = "",
          TemplateTypeParm = "󰊄",
          TemplateTemplateParm = "󰊄",
          TemplateParamObject = "󰊄",
        },
      },
    },
    config = function() end,
  },
  {
    "neovim/nvim-lspconfig",
    dependencies = {
      "p00f/clangd_extensions.nvim",
    },
    opts = function(_, opts)
      opts.servers = opts.servers or {}
      opts.servers.clangd = vim.tbl_deep_extend("force", {
        cmd = {
          "clangd",
          "--background-index",
          "--clang-tidy",
          "--header-insertion=iwyu",
          "--completion-style=detailed",
          "--function-arg-placeholders",
          "--fallback-style=llvm",
        },
        init_options = {
          usePlaceholders = true,
          completeUnimported = true,
          clangdFileStatus = true,
        },
        capabilities = {
          offsetEncoding = { "utf-16" },
        },
        keys = {
          {
            "<leader>ch",
            "<cmd>LspClangdSwitchSourceHeader<cr>",
            desc = "Switch Source/Header (C/C++)",
            has = "textDocument/switchSourceHeader",
          },
        },
        root_markers = {
          "compile_commands.json",
          "compile_flags.txt",
          "configure.ac",
          "meson.build",
          "build.ninja",
          ".clangd",
          ".clang-tidy",
          ".clang-format",
          "Makefile",
          "configure.in",
          "config.h.in",
          "meson_options.txt",
          ".git",
        },
      }, opts.servers.clangd or {})

      opts.setup = opts.setup or {}
      opts.setup.clangd = function(_, server_opts)
        local clangd_opts = require("util").opts("clangd_extensions.nvim") or {}
        require("clangd_extensions").setup(vim.tbl_deep_extend("force", clangd_opts, { server = server_opts }))
        return false
      end
    end,
  },
  {
    "saghen/blink.cmp",
    optional = true,
    opts = function(_, opts)
      opts.sorting = opts.sorting or {}
      opts.sorting.comparators = opts.sorting.comparators or {}
      table.insert(opts.sorting.comparators, 1, require("clangd_extensions.cmp_scores"))
    end,
  },
}
