local fs_util = require("util.fs")
local web_toolchain = require("util.web_toolchain")

local ft_js = {
  "tsx",
  "jsx",
  "javascript",
  "javascriptreact",
  "javascript.jsx",
  "typescript",
  "typescriptreact",
  "typescript.tsx",
}

local runtime_extension_path_markers = {
  "/home/dot_pi/agent/extensions/",
  "/home/dot_omp/private_agent/extensions/",
  "/.pi/agent/extensions/",
  "/.omp/agent/extensions/",
}

local function is_runtime_extension_false_positive(diagnostic)
  local code = tonumber(diagnostic.code)
  local message = diagnostic.message or ""
  if code == 2307 then
    return message:find("@earendil-works/pi-coding-agent", 1, true) ~= nil
      or message:find("@oh-my-pi/pi-coding-agent", 1, true) ~= nil
      or message:find("'node:", 1, true) ~= nil
  end
  if code == 2580 or code == 2591 then
    return message:find("'node:", 1, true) ~= nil
      or message:find("'process'", 1, true) ~= nil
      or message:find("'Buffer'", 1, true) ~= nil
  end
  if code == 7006 then
    return message == "Parameter 'code' implicitly has an 'any' type."
      or message == "Parameter 'event' implicitly has an 'any' type."
      or message == "Parameter 'ctx' implicitly has an 'any' type."
  end
  return false
end

local function is_runtime_extension_uri(uri)
  if type(uri) ~= "string" then
    return false
  end
  local path = vim.uri_to_fname(uri):gsub("\\", "/")
  for _, marker in ipairs(runtime_extension_path_markers) do
    if path:find(marker, 1, true) then
      return true
    end
  end
  return false
end

local function filter_runtime_extension_diagnostics(err, res, ctx, config)
  if res and is_runtime_extension_uri(res.uri) and type(res.diagnostics) == "table" then
    res.diagnostics = vim.tbl_filter(function(diagnostic)
      local is_typescript_diagnostic = diagnostic.source == "tsserver" or diagnostic.source == "typescript"
      return not is_typescript_diagnostic or not is_runtime_extension_false_positive(diagnostic)
    end, res.diagnostics)
  end
  vim.lsp.diagnostic.on_publish_diagnostics(err, res, ctx, config)
end

return {
  {
    "nvim-treesitter/nvim-treesitter",
    opts = function(_, opts)
      opts.ensure_installed =
        vim.list_extend(opts.ensure_installed or {}, { "typescript", "tsx", "javascript", "jsx", "jsdoc" })
      return opts
    end,
  },
  {
    "mason-org/mason.nvim",
    opts = function(_, opts)
      opts.ensure_installed = vim.list_extend(
        opts.ensure_installed or {},
        { "biome", "oxfmt", "oxlint", "prettierd", "prettier", "typescript-language-server" }
      )
      return opts
    end,
  },
  {
    "pmizio/typescript-tools.nvim",
    version = false,
    cond = function()
      return vim.env.NVIM_MUSIC == nil
    end,
    keys = {
      {
        "gR",
        "<cmd>TSToolsFileReferences<cr>",
        ft = ft_js,
        desc = "TSTools: File References",
        buffer = true,
      },
    },
    dependencies = {
      "nvim-lua/plenary.nvim",
      {
        "neovim/nvim-lspconfig",
        dependencies = {
          { "b0o/SchemaStore.nvim" },
        },
        opts = function(_, opts)
          opts.servers = opts.servers or {}
          opts.servers.ts_ls = { enabled = false }
          opts.servers.tsserver = { enabled = false } -- @deprecated

          opts.servers["*"] = opts.servers["*"] or {}
          opts.servers["*"].keys = opts.servers["*"].keys or {}

          table.insert(opts.servers["*"].keys, {
            "<leader>cR",
            function()
              if vim.tbl_contains(ft_js, vim.bo.filetype) then
                vim.cmd("TSToolsRenameFile")
              else
                vim.lsp.buf.rename()
              end
            end,
            desc = "Rename File",
            has = "rename",
          })

          opts.setup = opts.setup or {}
          opts.setup.tsserver = function()
            -- disable tsserver
            return true
          end
          opts.setup.ts_ls = function()
            -- disable ts_ls
            return true
          end

          return opts
        end,
      },
    },
    ft = ft_js,
    opts = {
      handlers = {
        ["textDocument/publishDiagnostics"] = filter_runtime_extension_diagnostics,
      },
      settings = {
        code_lens = "off",
        complete_function_calls = false,
        include_completions_with_insert_text = true,
        separate_diagnostic_server = true,
        publish_diagnostic_on = "insert_leave",
        tsserver_path = nil,
        tsserver_max_memory = 32000,
        tsserver_format_options = {
          allowIncompleteCompletions = false,
        },
        tsserver_file_preferences = {
          completions = { completeFunctionCalls = false },
          includeInlayParameterNameHints = "none",
          includeCompletionsForModuleExports = true,
          init_options = {
            preferences = {
              disableSuggestions = true,
            },
          },
          importModuleSpecifierPreference = "project-relative",
          jsxAttributeCompletionStyle = "braces",
        },
        tsserver_locale = "en",
        disable_member_code_lens = true,
        jsx_close_tag = { enable = false },
      },
      root_dir = function(bufnr, onDir)
        onDir(fs_util.get_project_root())
      end,
    },
  },
  {
    "dmmulroy/tsc.nvim",
    opts = {
      auto_start_watch_mode = false,
      use_trouble_qflist = false,
      flags = {
        watch = false,
      },
    },
    keys = {
      { "<leader>cttc", ft = { "typescript", "typescriptreact" }, "<cmd>TSC<cr>", desc = "Type Check" },
      { "<leader>cttq", ft = { "typescript", "typescriptreact" }, "<cmd>TSCOpen<cr>", desc = "Type Check Quickfix" },
    },
    ft = {
      "typescript",
      "typescriptreact",
    },
    cmd = {
      "TSC",
      "TSCOpen",
      "TSCClose",
    },
  },
  {
    "nvim-mini/mini.icons",
    opts = {
      file = {
        [".eslintrc.js"] = { glyph = "󰱺", hl = "MiniIconsYellow" },
        [".node-version"] = { glyph = "", hl = "MiniIconsGreen" },
        [".prettierrc"] = { glyph = "", hl = "MiniIconsPurple" },
        [".yarnrc.yml"] = { glyph = "", hl = "MiniIconsBlue" },
        ["eslint.config.js"] = { glyph = "󰱺", hl = "MiniIconsYellow" },
        ["package.json"] = { glyph = "", hl = "MiniIconsGreen" },
        ["tsconfig.json"] = { glyph = "", hl = "MiniIconsAzure" },
        ["tsconfig.build.json"] = { glyph = "", hl = "MiniIconsAzure" },
        ["yarn.lock"] = { glyph = "", hl = "MiniIconsBlue" },
      },
    },
  },
  {
    "stevearc/conform.nvim",
    opts = function(_, opts)
      opts.formatters_by_ft = vim.tbl_deep_extend("force", opts.formatters_by_ft or {}, {
        javascript = web_toolchain.web_formatters,
        javascriptreact = web_toolchain.web_formatters,
        typescript = web_toolchain.web_formatters,
        typescriptreact = web_toolchain.web_formatters,
        vue = web_toolchain.web_formatters,
        svelte = web_toolchain.web_formatters,
        astro = web_toolchain.web_formatters,
      })
      return opts
    end,
  },
  {
    "mfussenegger/nvim-lint",
    optional = true,
    opts = function(_, opts)
      opts.linters_by_ft = vim.tbl_deep_extend("force", opts.linters_by_ft or {}, {
        javascript = { "oxlint" },
        javascriptreact = { "oxlint" },
        typescript = { "oxlint" },
        typescriptreact = { "oxlint" },
        vue = { "oxlint" },
        svelte = { "oxlint" },
        astro = { "oxlint" },
      })

      -- Only enable oxlint when a repo explicitly opts into it.
      -- (nvim-lint will call this with { filename, dirname }).
      opts.linters = opts.linters or {}
      opts.linters.oxlint = vim.tbl_deep_extend("force", opts.linters.oxlint or {}, {
        condition = function(ctx)
          if not ctx or type(ctx.dirname) ~= "string" or ctx.dirname == "" then
            return false
          end
          local found = vim.fs.find({ ".oxlintrc.json", ".oxlintrc.jsonc", "oxlint.config.ts" }, {
            path = ctx.dirname,
            upward = true,
          })[1]
          return found ~= nil
        end,
      })

      return opts
    end,
  },
}
