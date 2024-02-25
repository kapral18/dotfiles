vim.filetype.add({
  extension = { mdx = "mdx" },
})

return {
  {
    "williamboman/mason.nvim",
    opts = function(_, opts)
      vim.list_extend(opts.ensure_installed, {
        "mdx-analyzer",
      })
    end,
  },
}
