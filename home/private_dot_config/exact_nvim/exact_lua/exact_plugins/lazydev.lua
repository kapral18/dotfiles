return {
  { "LuaCATS/luassert", name = "luassert-types", lazy = true },
  { "LuaCATS/busted", name = "busted-types", lazy = true },
  {
    "folke/lazydev.nvim",
    lazy = false,
    opts = function(_, opts)
      vim.list_extend(opts.library, {
        -- { path = vim.env.VIMRUNTIME .. "/lua", words = { "vim%." } },
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
      })
    end,
  },
}
