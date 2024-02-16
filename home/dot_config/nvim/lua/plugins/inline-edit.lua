return {
  -- Plugin for editing inline scripts in html, ruby, md, etc.
  {
    "AndrewRadev/inline_edit.vim",
    lazy = true,
    cmd = { "InlineEdit" },
    keys = {
      { "<leader>ce", "<cmd>InlineEdit<cr>", desc = "Inline Edit (for ex. JS inside <script> html)" },
    },
    init = function()
      vim.g.inline_edit_autowrite = 1 -- Automatically save target buffer as well when buffer is saved
    end,
  },
}
