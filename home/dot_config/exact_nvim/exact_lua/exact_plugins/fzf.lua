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
      {
        "<leader>sb",
        function()
          require("snipe").open_buffer_menu()
        end,
        desc = "Open Snipe buffer menu",
      },
      { "<leader>,",       function() require("snacks").picker.buffers() end,                                                   desc = "Buffers", },
      { "<leader>.",       function() require("snacks").scratch() end,                                                          desc = "Toggle Scratch Buffer", },
      { "<leader><space>", get_fzf_fn("files", { cwd = vim.uv.cwd() }),                                                         desc = "Files" },
      { "<leader>i",       get_fzf_fn("files", { fd_opts = fd_opts_unrestricted, cwd = vim.uv.cwd() }),                         desc = "Files" },
      { "<leader>/",       get_fzf_fn("lgrep_curbuf"),                                                                          desc = "Grep" },
      { "<leader>:",       "<cmd>Telescope command_history<cr>",                                                                desc = "Command History" },
      { "<leader>sg",      function() require("fzf-lua").live_grep({ rg_opts = rg_opts, cwd = vim.uv.cwd() }) end,              desc = "Live Grep", },
      { "<leader>sG",      function() require("fzf-lua").live_grep({ rg_opts = rg_opts_unrestricted, cwd = vim.uv.cwd() }) end, desc = "Live Grep (+ ignored)", },
      {
        "<leader>fr",
        function()
          require("snacks").picker.recent({
            filter = {
              cwd = true,
              paths = {
                [vim.fn.stdpath("data")] = false,
                [vim.fn.stdpath("cache")] = false,
                [vim.fn.stdpath("state")] = false,
                [vim.fn.getcwd() .. '.git/objects'] = false,
                [vim.fn.getcwd() .. '.git/refs'] = false,
                [vim.fn.getcwd() .. '.git/logs'] = false,
                [vim.fn.getcwd() .. '.git/rr-cache'] = false
              }
            }
          })
        end,
        desc = "Recent (cwd)"
      },
      { "<leader>sR",  function() require("snacks").picker.resume() end,             desc = "Resume Picker List" },
      { "<leader>sh",  function() require("snacks").picker.help() end,               desc = "Help Pages" },
      { "<leader>sk",  function() require("snacks").picker.keymaps() end,            desc = "Key Maps" },
      { "<leader>sc",  function() require("snacks").picker.commands() end,           desc = "Commands" },
      { "<leader>sa",  function() require("snacks").picker.autocmds() end,           desc = "Auto Commands" },
      { "<leader>sC",  function() require("snacks").picker.colorschemes() end,       desc = "Colorscheme with Preview" },
      { "<leader>sm",  function() require("snacks").picker.marks() end,              desc = "Jump to Mark" },
      { "<leader>sH",  function() require("snacks").picker.highlights() end,         desc = "Search Highlight Groups" },
      { "<leader>s\"", function() require("snacks").picker.registers() end,          desc = "Registers", },
      { "<leader>s/",  function() require("snacks").picker.search_history() end,     desc = "Search History", },
      { "<leader>sB",  function() require("snacks").picker.grep_buffers() end,       desc = "Grep Open Buffers", },
      { "<leader>sd",  function() require("snacks").picker.diagnostics() end,        desc = "Diagnostics", },
      { "<leader>sD",  function() require("snacks").picker.diagnostics_buffer() end, desc = "Buffer Diagnostics", },
      { "<leader>si",  function() require("snacks").picker.icons() end,              desc = "Icons", },
      { "<leader>sj",  function() require("snacks").picker.jumps() end,              desc = "Jumps", },
      { "<leader>sM",  function() require("snacks").picker.man() end,                desc = "Man Pages", },
      { "<leader>sp",  function() require("snacks").picker.lazy() end,               desc = "Search for Plugin Spec", },
      { "<leader>sq",  function() require("snacks").picker.qflist() end,             desc = "Quickfix List", },
      { "<leader>sl",  function() require("snacks").picker.loclist() end,            desc = "Location List", },
      {
        "<leader>sw",
        function()
          require("fzf-lua").live_grep({
            search = vim.fn.expand("<cword>"),
            rg_opts = rg_opts,
            no_esc = true,
            cwd =
                vim.uv.cwd(),
          })
        end,
        desc = "Live Grep CWord",
      },
      {
        "<leader>sW",
        function()
          require("fzf-lua").live_grep({
            search = vim.fn.expand("<cword>"),
            rg_opts =
                rg_opts_unrestricted,
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
            search = vim.trim(require("fzf-lua").utils
              .get_visual_selection()),
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
            search = vim.trim(require("fzf-lua").utils
              .get_visual_selection()),
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
