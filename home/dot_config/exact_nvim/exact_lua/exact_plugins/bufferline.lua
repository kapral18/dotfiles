return {
  {
    "akinsho/bufferline.nvim",
    -- switched off for performance reasons
    enabled = false,
  },
  {
    "echasnovski/mini.tabline",
    lazy = false, -- load plugin immediately  otherwise it's not shown in the tabline
    version = "*",
    dependencies = {
      { "echasnovski/mini.icons", opts = {} },
    },
    opts = {
      tabpage_section = "right",
      format = function(buf_id, label)
        local MiniTabline = require("mini.tabline")
        local suffix = vim.bo[buf_id].modified and "● " or ""
        return MiniTabline.default_format(buf_id, label) .. suffix
      end,
      -- Whether to show file icons (requires 'mini.icons')
      show_icons = false,
      -- Whether to set Vim's settings for tabline (make it always shown and
      -- allow hidden buffers)
      set_vim_settings = true,
    },
    config = function(_, opts)
      require("mini.tabline").setup(opts)
      vim.o.tabline = "%!v:lua.MiniTabline.make_tabline_string()"
      vim.o.showtabline = 2
    end,
    keys = {
      { "<A-h>", "<cmd>bprevious<CR>", { desc = "Previous buffer" } },
      { "<A-l>", "<cmd>bnext<CR>", { desc = "Next buffer" } },
    },
  },
}
