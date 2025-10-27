local util = require("util")

local function get_fzf_fn(cmd, opts)
  opts = opts or {}
  return function()
    require("fzf-lua")[cmd](opts)
  end
end

local rg_opts = util.fzf_rg_opts
local rg_opts_unrestricted = util.fzf_rg_opts_unrestricted
local fd_opts_unrestricted = util.fzf_fd_opts_unrestricted

local function get_telescope_fn(cmd, opts)
  opts = opts or {}
  return function()
    require("telescope.builtin")[cmd](opts)
  end
end

return {
  {
    "ibhagwan/fzf-lua",
    dependencies = {
      { "nvim-tree/nvim-web-devicons" },
      { "nvim-telescope/telescope.nvim" },
      {
        "leath-dub/snipe.nvim",
        opts = {
          navigate = {
            cancel_snipe = "q",
          },
        },
      },
    },
    keys = {
      { "<leader>,",       false },
      {
        "<leader>sb",
        function()
          require("snipe").open_buffer_menu()
        end,
        desc = "Open Snipe buffer menu",
      },
      { "<leader>:",       "<cmd>Telescope command_history<cr>",                                        desc = "Command History" },
      { "<leader><space>", get_fzf_fn("files", { cwd = vim.uv.cwd() }),                                 desc = "Files" },
      { "<leader>i",       get_fzf_fn("files", { fd_opts = fd_opts_unrestricted, cwd = vim.uv.cwd() }), desc = "Files" },
      { "<leader>fr",      get_fzf_fn("oldfiles", { cwd = vim.uv.cwd() }),                              desc = "Recent (cwd)" },
      { "<leader>fR",      "<cmd>Telescope oldfiles<cr>",                                               desc = "Recent (all)" },
      { "<leader>/",       get_fzf_fn("lgrep_curbuf"),                                                  desc = "Grep" },
      {
        "<leader>sg",
        function()
          require("fzf-lua").live_grep({ rg_opts = rg_opts, cwd = vim.uv.cwd() })
        end,
        desc = "Live Grep",
      },
      {
        "<leader>sG",
        function()
          require("fzf-lua").live_grep({ rg_opts = rg_opts_unrestricted, cwd = vim.uv.cwd() })
        end,
        desc = "Live Grep (+ ignored)",
      },
      { "<leader>sR", get_fzf_fn("resume"),       desc = "Resume Picker List" },
      { "<leader>sh", get_fzf_fn("help_tags"),    desc = "Help Pages" },
      { "<leader>sk", get_fzf_fn("keymaps"),      desc = "Key Maps" },
      { "<leader>sc", get_fzf_fn("commands"),     desc = "Commands" },
      { "<leader>sa", get_fzf_fn("autocmds"),     desc = "Auto Commands" },
      { "<leader>sC", get_fzf_fn("colorschemes"), desc = "Colorscheme with Preview" },
      { "<leader>sm", get_fzf_fn("marks"),        desc = "Jump to Mark" },
      { "<leader>sH", get_fzf_fn("highlights"),   desc = "Search Highlight Groups" },
      {
        "<leader>sw",
        function()
          require("fzf-lua").live_grep({
            search = vim.fn.expand("<cword>"),
            rg_opts = rg_opts,
            no_esc = true,
            cwd = vim.uv.cwd(),
          })
        end,
        desc = "Live Grep CWord",
      },
      {
        "<leader>sW",
        function()
          require("fzf-lua").live_grep({
            search = vim.fn.expand("<cword>"),
            rg_opts = rg_opts_unrestricted,
            no_esc = true,
            cwd = vim.uv.cwd(),
          })
        end,
        desc = "Live Grep CWord (+ ignored)",
      },
      {
        "<leader>sw",
        function()
          require("fzf-lua").live_grep({
            search = vim.trim(require("fzf-lua").utils.get_visual_selection()),
            rg_opts = rg_opts .. " --multiline",
            no_esc = false,
            cwd = vim.uv.cwd(),
          })
        end,
        mode = "v",
        desc = "Live Grep Selection",
      },
      {
        "<leader>sW",
        function()
          require("fzf-lua").live_grep({
            search = vim.trim(require("fzf-lua").utils.get_visual_selection()),
            rg_opts = rg_opts_unrestricted .. " --multiline",
            no_esc = false,
            cwd = vim.uv.cwd(),
          })
        end,
        mode = "v",
        desc = "Live Grep Selection (+ignored)",
      },
    },
    opts = util.get_fzf_opts(),
    config = function(_, opts)
      require("fzf-lua").setup(opts)
      -- Register fzf-lua as the vim.ui.select provider for LSP pickers
      require("fzf-lua").register_ui_select()
    end,
  },
}
