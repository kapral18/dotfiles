local common_utils = require("utils.common")

local function get_fzf_fn(cmd, opts)
  opts = opts or {}
  return function()
    require("fzf-lua")[cmd](opts)
  end
end

local rg_opts, rg_opts_unrestricted = common_utils.get_fzf_rg_opts()
local fd_opts_unrestricted = common_utils.get_fzf_fd_opts()

local function get_telescope_fn(cmd, opts)
  opts = opts or {}
  return function()
    require("telescope.builtin")[cmd](opts)
  end
end

local function live_grep_with_patterns(initial_search, opts)
  local search_patterns = {
    initial_search,
    [[\b]]
      .. initial_search
      .. [[\b -- **/*.ts **/*.tsx !*.d.ts !*.test.ts !*.test.tsx !**/__mocks__/* !**/__jest__/* !**/fixtures/* !**/test/* !**/mock/*]],
    [[\b]] .. initial_search .. [[\b -- **/*.ts **/*.tsx !*.d.ts]],
  }
  local current_index = 1

  local function cycle_current_index()
    current_index = (current_index % #search_patterns) + 1
  end

  local function nested_live_grep()
    require("fzf-lua").live_grep(vim.tbl_deep_extend("force", {
      rg_glob = true,
      no_esc = true,
      actions = {
        ["ctrl-g"] = { nested_live_grep }, -- No need to pass rg_opts here
      },
      search = search_patterns[current_index],
      ["keymap.fzf.start"] = "beginning-of-line+forward-char+forward-char",
    }, opts))

    cycle_current_index()
  end

  nested_live_grep()
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
      { "<leader>,", false },
      {
        "<leader>sb",
        function()
          require("snipe").open_buffer_menu()
        end,
        desc = "Open Snipe buffer menu",
      },
      { "<leader>:", "<cmd>Telescope command_history<cr>", desc = "Command History" },
      { "<leader><space>", get_fzf_fn("files", { cwd = vim.uv.cwd() }), desc = "Files" },
      { "<leader>i", get_fzf_fn("files", { fd_opts = fd_opts_unrestricted, cwd = vim.uv.cwd() }), desc = "Files" },
      { "<leader>fr", get_fzf_fn("oldfiles", { cwd = vim.uv.cwd() }), desc = "Recent (cwd)" },
      { "<leader>fr", get_telescope_fn("oldfiles", { cwd = vim.uv.cwd() }), desc = "Recent (cwd)" },
      { "<leader>fR", "<cmd>Telescope oldfiles<cr>", desc = "Recent (all)" },
      { "<leader>/", get_fzf_fn("lgrep_curbuf"), desc = "Grep" },
      {
        "<leader>sg",
        function()
          live_grep_with_patterns("", { cwd = vim.uv.cwd() })
        end,
        desc = "Live Grep",
      },
      {
        "<leader>sG",
        function()
          live_grep_with_patterns("", { cwd = vim.uv.cwd() })
        end,
        desc = "Live Grep (+ ignored)",
      },
      { "<leader>sR", get_fzf_fn("resume"), desc = "Resume Picker List" },
      {
        "<leader>sw",
        function()
          live_grep_with_patterns(vim.fn.expand("<cword>"), { rg_opts = rg_opts, cwd = vim.uv.cwd() })
        end,
        desc = "Live Grep CWord",
      },
      {
        "<leader>sW",
        function()
          live_grep_with_patterns(vim.fn.expand("<cword>"), { rg_opts = rg_opts_unrestricted, cwd = vim.uv.cwd() })
        end,
        desc = "Live Grep CWord (+ ignored)",
      },
      {
        "<leader>sw",
        function()
          live_grep_with_patterns(
            vim.trim(require("fzf-lua").utils.get_visual_selection()),
            { rg_opts = rg_opts .. " --multiline", no_esc = false, cwd = vim.uv.cwd() }
          )
        end,
        mode = "v",
        desc = "Live Grep Selection",
      },
      {
        "<leader>sW",
        function()
          live_grep_with_patterns(
            vim.trim(require("fzf-lua").utils.get_visual_selection()),
            { rg_opts = rg_opts_unrestricted .. " --multiline", no_esc = false, cwd = vim.uv.cwd() }
          )
        end,
        mode = "v",
        desc = "Live Grep Selection (+ignored)",
      },
    },
    opts = common_utils.get_fzf_opts(),
  },
}
