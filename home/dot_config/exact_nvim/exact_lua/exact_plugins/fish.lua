return {
  {
    "nvim-treesitter/nvim-treesitter",
    opts = function(_, opts)
      vim.list_extend(opts.ensure_installed, {
        "fish",
      })
    end,
  },
  {
    "ndonfris/fish-lsp",
    dependencies = {
      "neovim/nvim-lspconfig",
    },
    ft = { "fish" },
    config = function()
      require("lspconfig").fish_lsp.setup({
        cmd = { "fish-lsp", "start" },
        cmd_env = { fish_lsp_show_client_popups = false },
        filetypes = { "fish" },
      })
      -- Create a group for FishLSP autocommands
      local fish_group = vim.api.nvim_create_augroup("FishLSP", { clear = true })

      -- Document highlighting on CursorHold events
      vim.api.nvim_create_autocmd({ "CursorHold", "CursorHoldI" }, {
        group = fish_group,
        pattern = "*.fish",
        callback = function()
          vim.lsp.buf.document_highlight()
        end,
      })

      -- Clear references on CursorMoved for fish files
      vim.api.nvim_create_autocmd("CursorMoved", {
        group = fish_group,
        pattern = "*.fish",
        callback = function()
          vim.lsp.buf.clear_references()
        end,
      })
    end,
  },
}
