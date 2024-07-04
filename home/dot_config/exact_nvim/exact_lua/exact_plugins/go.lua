return {
  { import = "lazyvim.plugins.extras.lang.go" },
  {
    "ray-x/go.nvim",
    ft = { "go", "gomod", "gosum", "gowork", "gotmpl" },
    dependencies = {
      {
        "ray-x/guihua.lua",
        build = "cd lua/fzy && make",
      },
    },
    opts = function()
      vim.api.nvim_set_hl(0, "goCoverageUncover", { fg = "#f9e2af" })
      vim.api.nvim_set_hl(0, "goCoverageUncovered", { fg = "#F38BA8" })
      vim.api.nvim_set_hl(0, "goCoverageCovered", { fg = "#a6e3a1" })
      return {
        lsp_inlay_hints = {
          enable = false,
          -- only_current_line = true,
          other_hints_prefix = "•",
        },
        trouble = true,
        lsp_keymaps = false,
        diagnostic = {
          hdlr = true,
          underline = true,
          virtual_text = false,
          signs = true,
          update_in_insert = false,
        },
        lsp_codelens = true,
        floaterm = {
          posititon = "auto",
          width = 0.45,
          height = 0.98,
          title_colors = "dracula",
        },
        icons = { breakpoint = "", currentpos = "" },
        gocoverage_sign = "│",
        -- lsp_diag_virtual_text = { space = 0, prefix = "" },
        --  cat
        dap_debug_vt = { enabled_commands = true, all_frames = true },
      }
    end,
    build = ':lua require("go.install").update_all_sync()',
  },
}
