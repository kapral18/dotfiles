return {
  "jbyuki/venn.nvim",
  keys = {
    {
      mode = "n",
      "<leader>v",
      function()
        local venn_enabled = vim.inspect(vim.b.venn_enabled)
        if venn_enabled == "nil" then
          vim.b.venn_enabled = true
          vim.opt_local.ve = "all"
          vim.keymap.set("n", "H", "<C-v>h:VBox<CR>", { buffer = true })
          vim.keymap.set("n", "J", "<C-v>j:VBox<CR>", { buffer = true })
          vim.keymap.set("n", "K", "<C-v>k:VBox<CR>", { buffer = true })
          vim.keymap.set("n", "L", "<C-v>l:VBox<CR>", { buffer = true })
          vim.keymap.set("x", "vb", ":VBox<CR>", { buffer = true })
          vim.keymap.set("x", "vf", ":VFill<CR>", { buffer = true })
          vim.keymap.set("x", "vo", ":VBoxO<CR>", { buffer = true })
          return
        end

        vim.opt_local.ve = ""
        vim.keymap.del("n", "H", { buffer = true })
        vim.keymap.del("n", "J", { buffer = true })
        vim.keymap.del("n", "K", { buffer = true })
        vim.keymap.del("n", "L", { buffer = true })
        vim.keymap.del("x", "vb", { buffer = true })
        vim.keymap.del("x", "vf", { buffer = true })
        vim.keymap.del("x", "vo", { buffer = true })
        vim.b.venn_enabled = nil
      end,
    },
  },
}
