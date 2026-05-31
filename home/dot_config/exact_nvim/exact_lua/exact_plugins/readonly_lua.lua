return {
  {
    "nvim-treesitter/nvim-treesitter",
    opts = function(_, opts)
      opts.ensure_installed = vim.list_extend(opts.ensure_installed or {}, { "lua", "luadoc", "luap" })
      return opts
    end,
  },
  {
    "mason-org/mason.nvim",
    opts = function(_, opts)
      opts.ensure_installed = vim.list_extend(opts.ensure_installed or {}, { "stylua" })
      return opts
    end,
  },
  {
    "neovim/nvim-lspconfig",
    dependencies = {
      "folke/lazydev.nvim", -- Ensure lazydev loads first
    },
    opts = {
      servers = {
        lua_ls = {
          -- Native nvim LSP (>= 0.11) `root_dir` is `fun(bufnr, on_dir)`: the
          -- chosen root must be passed to `on_dir`, not returned. The old
          -- lspconfig `fun(fname) -> root` signature is silently ignored here,
          -- which let lua_ls fall back to its `.git` root_marker and index the
          -- entire chezmoi source tree (100k+ files -> stuck at 0%).
          root_dir = function(bufnr, on_dir)
            local fname = vim.api.nvim_buf_get_name(bufnr)
            if fname == "" then
              return
            end

            -- A real lua_ls project marker always wins.
            local luarc_root = vim.fs.root(fname, { ".luarc.json", ".luarc.jsonc" })
            if luarc_root then
              return on_dir(luarc_root)
            end

            -- Narrow chezmoi-source files to their own directory BEFORE falling
            -- back to weaker markers. The chezmoi repo root carries a
            -- `.stylua.toml` and a `.git`, both of which would otherwise root
            -- lua_ls at the 30k-file source tree and hang preload (stuck at 0%).
            local git_root = vim.fs.root(fname, ".git")
            local chezmoi_src = vim.g["chezmoi#source_dir_path"] or vim.env.CHEZMOI_SOURCE_DIR
            if git_root and chezmoi_src and vim.startswith(git_root, chezmoi_src) then
              return on_dir(vim.fs.dirname(fname))
            end

            -- Outside chezmoi: formatter/linter configs, then the git root.
            local marker_root = vim.fs.root(fname, { ".stylua.toml", "stylua.toml", "selene.toml" })
            return on_dir(marker_root or git_root or vim.fs.dirname(fname))
          end,
          capabilities = {
            documentFormattingProvider = false,
            documentRangeFormattingProvider = false,
          },
          settings = {
            Lua = {
              workspace = {
                checkThirdParty = false,
                useGitIgnore = true,
                maxPreload = 1500,
                preloadFileSize = 200,
                library = {
                  string.format("%s/.hammerspoon/Spoons/EmmyLua.spoon/annotations", os.getenv("HOME")),
                },
              },
              completion = {
                callSnippet = "Replace",
              },
              runtime = {
                version = "LuaJIT",
              },
              hint = {
                enable = false,
                setType = true,
              },
              diagnostics = {
                globals = { "vim", "hs", "spoon" },
              },
              telemetry = {
                enable = false,
              },
            },
          },
        },
      },
    },
  },
  {
    "stevearc/conform.nvim",
    opts = function(_, opts)
      opts.formatters_by_ft = vim.tbl_deep_extend("force", opts.formatters_by_ft or {}, {
        lua = { "stylua" },
      })
      return opts
    end,
  },
}
