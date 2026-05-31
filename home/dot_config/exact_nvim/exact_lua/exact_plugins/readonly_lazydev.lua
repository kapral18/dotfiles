return {
  { "LuaCATS/luassert", name = "luassert-types", version = false },
  { "LuaCATS/busted", name = "busted-types", version = false },
  {
    "folke/lazydev.nvim",
    version = "*",
    cmd = "LazyDev",
    opts = function(_, opts)
      -- Disable lazydev's lspconfig integration. Its only job is to override
      -- lua_ls `root_dir` with `find_workspace`, which for a fresh buffer
      -- returns nil and lets native LSP fall back to the `.git` root_marker.
      -- In this chezmoi repo that roots lua_ls at the 30k-file source tree and
      -- hangs the workspace preload (stuck at 0%). Our own `root_dir` in
      -- `plugins/lua.lua` narrows chezmoi-source files to their own directory;
      -- this keeps that in control. Library injection is unaffected (it runs
      -- through lazydev's buffer/workspace mechanism, not this integration).
      opts.integrations = vim.tbl_deep_extend("force", opts.integrations or {}, {
        lspconfig = false,
      })
      opts.library = opts.library or {}
      vim.list_extend(opts.library, {
        { path = "${3rd}/luv/library", words = { "vim%.uv" } },
        { path = "luassert-types/library", words = { "assert" } },
        { path = "busted-types/library", words = { "describe" } },
        {
          path = "plenary.nvim",
          words = {
            "before_each",
            "after_each",
            "describe",
            "it",
            "pending",
            "clear",
          },
        },
        { path = vim.fn.expand("~/.hammerspoon/Spoons/EmmyLua.spoon/annotations"), words = { "hs" } },
      })
    end,
  },
}
