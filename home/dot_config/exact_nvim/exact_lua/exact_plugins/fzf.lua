local winopts = {
  small = {
    no_preview = {
      height = 0.35,
      width = 0.65,
      preview = {
        hidden = "hidden",
      },
    },
  },
  medium = {
    flex = {
      height = 0.75,
      width = 0.75,
      preview = {
        layout = "flex",
      },
    },
    vertical = {
      height = 0.75,
      width = 0.75,
      preview = {
        layout = "vertical",
        vertical = "up:65%",
      },
    },
  },
  large = {
    vertical = {
      height = 0.9,
      width = 0.9,
      preview = {
        layout = "vertical",
        vertical = "up:65%",
      },
    },
  },
  full = {
    vertical = {
      fullscreen = true,
      preview = {
        layout = "vertical",
        vertical = "down:75%",
      },
    },
  },
}

local function get_fzf_fn(cmd, opts)
  opts = opts or {}
  return function()
    require("fzf-lua")[cmd](opts)
  end
end

local rg_ignore_glob =
  "-g '!{node_modules,.next,dist,build,reports,.idea,.vscode,.yarn,.nyc_output,__generated__,reports,storybook-static,*.min.js,*.min.css,junit.xml,bazel-*,data,target,.buildkite,.chromium,.es,.yarn-*}'"
local fd_ignore_glob =
  "-E '{node_modules,.next,dist,build,reports,.idea,.vscode,.yarn,.nyc_output,__generated__,reports,storybook-static}/' -E '{*.min.js,*.min.css,junit.xml,bazel-*,data,target,.buildkite,.chromium,.es,.yarn-*}'"

local rg_opts_unrestricted =
  "--column --line-number --no-heading --color=always --smart-case --max-columns=512 --hidden --no-ignore -g '!{.git,tsconfig.tsbuildinfo,*.map}'"

local rg_opts = rg_opts_unrestricted .. " " .. rg_ignore_glob

local fd_opts_unrestricted =
  "--color=never --type f --hidden --no-ignore --follow -E '{.git,tsconfig.tsbuildinfo,*.map}'"

local fd_opts = fd_opts_unrestricted .. " " .. fd_ignore_glob

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
      winopts = winopts.large.vertical,
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
    "nvim-telescope/telescope.nvim",
    keys = {

      {
        "<leader>,",
        false,
      },
      { "<leader>/", false },
      { "<leader><space>", false },
      { "<leader>fr", false },
      { "<leader>fR", false },
      { "<leader>sg", false },
      { "<leader>sG", false },
      { "<leader>sR", false },
      { "<leader>sw", false },
    },
  },
  {
    "ibhagwan/fzf-lua",
    dependencies = { "nvim-tree/nvim-web-devicons" },
    keys = {
      {
        "<leader><space>",
        get_fzf_fn("files", {
          winopts = winopts.medium.vertical,
        }),
        desc = "Files",
      },
      {
        "<leader>i",
        get_fzf_fn("files", {
          fd_opts = fd_opts_unrestricted,
          winopts = winopts.medium.vertical,
        }),
        desc = "Files",
      },
      {
        "<leader>fr",
        get_fzf_fn("oldfiles", {
          winopts = winopts.medium.vertical,
          cwd_only = true,
        }),
        desc = "Recent Files (Current Session)",
      },
      {
        "<leader>fR",
        get_fzf_fn("oldfiles", {
          winopts = winopts.medium.vertical,
          cwd_only = true,
          include_current_session = false,
        }),
        desc = "Recent Files (All Sessions)",
      },
      {
        "<leader>/",
        get_fzf_fn("lgrep_curbuf", {
          winopts = winopts.large.vertical,
        }),
        desc = "Grep",
      },
      {
        "<leader>sg",
        function()
          live_grep_with_patterns("", { rg_opts = rg_opts })
        end,
        desc = "Live Grep",
      },
      {
        "<leader>sG",
        function()
          live_grep_with_patterns("", { rg_opts = rg_opts_unrestricted })
        end,
        desc = "Live Grep (+ ignored)",
      },
      {
        "<leader>sR",
        get_fzf_fn("resume", { winopts = winopts.large.vertical }),
        desc = "Resume Picker List",
      },
      {
        "<leader>sw",
        function()
          live_grep_with_patterns(vim.fn.expand("<cword>"), {
            rg_opts = rg_opts,
            winopts = winopts.large.vertical,
          })
        end,
        desc = "Live Grep CWord",
      },
      {
        "<leader>sW",
        function()
          live_grep_with_patterns(vim.fn.expand("<cword>"), {
            rg_opts = rg_opts_unrestricted,
            winopts = winopts.large.vertical,
          })
        end,
        desc = "Live Grep CWord (+ ignored)",
      },
      {
        "<leader>sw",
        function()
          live_grep_with_patterns(vim.trim(require("fzf-lua").utils.get_visual_selection()), {
            rg_opts = rg_opts .. " --multiline",
            no_esc = false,
            winopts = winopts.large.vertical,
          })
        end,
        mode = "v",
        desc = "Live Grep Selection",
      },
      {
        "<leader>sW",
        function()
          live_grep_with_patterns(vim.trim(require("fzf-lua").utils.get_visual_selection()), {
            rg_opts = rg_opts_unrestricted .. " --multiline",
            no_esc = false,
            winopts = winopts.large.vertical,
          })
        end,
        mode = "v",
        desc = "Live Grep Selection (+ignored)",
      },
    },
    opts = function()
      local actions = require("fzf-lua").actions
      return {
        defaults = {
          git_icons = false,
          file_icons = false,
        },
        winopts = {
          height = 0.50,
          width = 0.75,
          preview = {
            default = "builtin",
            border = "noborder",
            wrap = "wrap",
            vertical = "down:45%",
            scrollbar = false,
            scrollchars = { "", "" },
            winopts = {
              number = false,
              relativenumber = false,
            },
          },
        },
        keymap = {
          fzf = {
            ["down"] = "down",
            ["up"] = "up",
            ["ctrl-c"] = "abort",
            ["ctrl-a"] = "toggle-all",
            ["ctrl-q"] = "select-all+accept",
            ["ctrl-d"] = "preview-page-down",
            ["ctrl-u"] = "preview-page-up",
          },
        },
        fzf_opts = {
          ["--prompt"] = "  ",
          ["--keep-right"] = false,
        },
        previewers = {
          bat = {
            cmd = "bat_preview",
            -- uncomment to set a bat theme, `bat --list-themes`
            theme = "Catppuccin-mocha",
          },
          builtin = {
            prompt = "Builtin❯ ",
            extensions = {
              -- neovim terminal only supports `viu` block output
              ["png"] = { "chafa" },
              ["jpg"] = { "chafa" },
              ["svg"] = { "chafa" },
              ["jpeg"] = { "chafa" },
              ["bpm"] = { "chafa" },
              ["tiff"] = { "chafa" },
              ["webp"] = { "chafa" },
              ["avif"] = { "chafa" },
            },
          },
        },
        files = {
          previewer = "bat",
          prompt = "Files❯ ",
          rg_opts = rg_opts,
          fd_opts = fd_opts,
          fzf_opts = { ["--ansi"] = false },
          actions = {
            ["ctrl-q"] = actions.file_sel_to_qf,
            ["ctrl-y"] = function(selected)
              print(selected[1])
            end,
            ["ctrl-r"] = { actions.toggle_ignore },
          },
        },
        grep = {
          previewer = "bat",
          prompt = "Live Grep❯ ",
          input_prompt = "Grep❯ ",
          rg_opts = rg_opts,
          actions = {
            ["ctrl-r"] = { actions.toggle_ignore },
          },
        },
      }
    end,
  },
}
