return {
  {
    "nvim-treesitter/nvim-treesitter",
    opts = function(_, opts)
      if type(opts.ensure_installed) == "table" then
        vim.list_extend(opts.ensure_installed, { "xml" })
      end
    end,
  },
  {
    "neovim/nvim-lspconfig",
    opts = {
      servers = {
        lemminx = {},
      },
    },
  },
  {
    "williamboman/mason.nvim",
    opts = function(_, opts)
      opts.ensure_installed = opts.ensure_installed or {}
      vim.list_extend(opts.ensure_installed, { "lemminx" })
    end,
  },
  {
    "nvim-lualine/lualine.nvim",
    optional = true,
    opts = function(_, opts)
      local function yaml_schema()
        local schema = require("yaml-companion").get_buf_schema(0)
        if schema.result[1].name == "none" then
          return ""
        end
        return schema.result[1].name
      end
      table.insert(opts.sections.lualine_x, 1, yaml_schema)
    end,
  },
}
