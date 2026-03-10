return {
  { "LuaCATS/luassert", name = "luassert-types", lazy = true },
  { "LuaCATS/busted", name = "busted-types", lazy = true },
  {
    "folke/lazydev.nvim",
    lazy = false,
    cmd = "LazyDev",
    opts = function(_, opts)
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
