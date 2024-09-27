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

local function symbols_filter(entry, ctx)
  ctx.symbols_filter = ctx.symbols_filter or require("lazyvim.config").get_kind_filter(ctx.bufnr)
  return vim.tbl_contains(ctx.symbols_filter, entry.kind)
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
      { "<leader>:", false },
      { "<leader><space>", false },
      { "<leader>ca", false },
      { "<leader>fb", false },
      { "<leader>fc", false },
      { "<leader>ff", false },
      { "<leader>fF", false },
      { "<leader>fr", false },
      { "<leader>fR", false },
      { "<leader>gc", false },
      { "<leader>gs", false },
      { "<leader>s", false },
      { "<leader>sa", false },
      { "<leader>sb", false },
      { "<leader>sc", false },
      { "<leader>sC", false },
      { "<leader>sd", false },
      { "<leader>sD", false },
      { "<leader>sg", false },
      { "<leader>sG", false },
      { "<leader>sh", false },
      { "<leader>sH", false },
      { "<leader>sk", false },
      { "<leader>sM", false },
      { "<leader>sm", false },
      { "<leader>so", false },
      { "<leader>sR", false },
      { "<leader>sw", false },
      { "<leader>sW", false },
      { "<leader>sw", false },
      { "<leader>sW", false },
      { "<leader>uC", false },
      {
        "<leader>ss",
        false,
      },
      {
        "<leader>sS",
        false,
      },
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
        "<leader>gs",
        get_fzf_fn("git_status", {
          winopts = winopts.large.vertical,
        }),
        desc = "Git Status",
      },
      {
        "<leader>gc",
        get_fzf_fn("git_commits", {
          winopts = winopts.large.vertical,
        }),
        desc = "Git Commits",
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
        "<leader>ss",
        get_fzf_fn("lsp_document_symbols", {
          winopts = winopts.large.vertical,
        }),
        desc = "Document Symbols",
      },
      {
        "<leader>sS",
        get_fzf_fn("lsp_live_workspace_symbols", {
          winopts = winopts.large.vertical,
        }),
        desc = "Workspace Symbols",
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
      { '<leader>s"', get_fzf_fn("registers", { winopts = winopts.large.vertical }), desc = "Registers" },
      {
        "<leader>sa",
        get_fzf_fn("autocmds", { winopts = winopts.large.vertical }),
        desc = "Auto Commands",
      },
      {
        "<leader>sc",
        get_fzf_fn("command_history", { winopts = winopts.large.vertical }),
        desc = "Command History",
      },
      { "<leader>sC", get_fzf_fn("commands", { winopts = winopts.large.vertical }), desc = "Commands" },
      {
        "<leader>sd",
        get_fzf_fn("diagnostics_document", { winopts = winopts.large.vertical }),
        desc = "Document Diagnostics",
      },
      {
        "<leader>sD",
        get_fzf_fn("diagnostics_workspace", { winopts = winopts.large.vertical }),
        desc = "Workspace Diagnostics",
      },
      { "<leader>sh", get_fzf_fn("help_tags", { winopts = winopts.large.vertical }), desc = "Help Pages" },
      {
        "<leader>sH",
        get_fzf_fn("highlights", { winopts = winopts.large.vertical }),
        desc = "Search Highlight Groups",
      },
      { "<leader>sm", get_fzf_fn("marks", { winopts = winopts.large.vertical }), desc = "Marks" },
      { "<leader>sk", get_fzf_fn("keymaps", { winops = winopts.large.vertical }), desc = "Key Maps" },
      { "<leader>sM", get_fzf_fn("man_pages", { winopts = winopts.large.vertical }), desc = "Man Pages" },
      -- { "<leader>so", "<cmd>Telescope vim_options<cr>", desc = "Options" },
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
      {
        "<leader>uC",
        get_fzf_fn("colorschemes", { winopts = winopts.large.vertical }),
        desc = "Colorscheme with preview",
      },
      {
        "<leader>sb",
        get_fzf_fn("buffers", { sort_mru = true, sort_lastused = true, winopts = winopts.large.vertical }),
        desc = "Buffers with preview",
      },
      {
        "<leader>ss",
        function()
          require("fzf-lua").lsp_document_symbols({
            regex_filter = symbols_filter,
          })
        end,
        desc = "Goto Symbol",
      },
      {
        "<leader>sS",
        function()
          require("fzf-lua").lsp_dynamic_workspace_symbols({
            regex_filter = symbols_filter,
          })
        end,
        desc = "Goto Symbol (Workspace)",
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
        marks = {
          prompt = "Marks❯ ",
        },
        changes = {
          prompt = "Changes❯ ",
        },
        jumps = {
          prompt = "Jumps❯ ",
        },
        tagstack = {
          prompt = "Tag Stack❯ ",
        },
        commands = {
          prompt = "Commands❯ ",
        },
        autocmds = {
          prompt = "Auto Commands❯ ",
        },
        command_history = {
          prompt = "Command History❯ ",
        },
        search_history = {
          prompt = "Search History❯ ",
        },
        registers = {
          prompt = "Registers❯ ",
        },
        keymaps = {
          prompt = "Keymaps❯ ",
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
        git = {
          files = {
            prompt = "Git Files❯ ",
          },
          status = {
            prompt = "Git Status❯ ",
          },
          commits = {
            prompt = "Git Commits❯ ",
          },
          bcommits = {
            prompt = "Git Buffer Commits❯ ",
          },
          branches = {
            prompt = "Git Branches❯ ",
          },
          tags = {
            prompt = "Git Tags❯ ",
          },
          stash = {
            prompt = "Git Stash❯ ",
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
        args = {
          prompt = "Args❯ ",
          actions = { ["ctrl-x"] = actions.arg_del },
        },
        oldfiles = {
          prompt = "History❯ ",
          include_current_session = true,
        },
        quickfix = {
          prompt = "Quickfix❯ ",
        },
        quickfix_stack = {
          prompt = "Quickfix Stack❯ ",
          marker = "❯",
        },
        loclist = {
          prompt = "Locations❯ ",
        },
        loclist_stack = {
          prompt = "Locations Stack❯ ",
          marker = "❯",
        },
        buffers = {
          prompt = "Buffers❯ ",
        },
        tabs = {
          prompt = "Tabs❯ ",
        },
        lines = {
          prompt = "Lines❯ ",
          actions = {
            ["ctrl-s"] = actions.file_split,
            ["ctrl-v"] = actions.file_vsplit,
            ["ctrl-t"] = actions.file_tabedit,
          },
        },
        blines = {
          prompt = "BLines❯ ",
          actions = {
            ["ctrl-s"] = actions.file_split,
            ["ctrl-v"] = actions.file_vsplit,
            ["ctrl-t"] = actions.file_tabedit,
          },
        },
        tags = {
          prompt = "Tags❯ ",
          input_prompt = "[tags] Grep For❯ ",
        },
        btags = {
          prompt = "Buffer Tags❯ ",
        },
        colorschemes = {
          prompt = "Colorschemes❯ ",
          winopts = { height = 0.55, width = 0.30 },
        },
        highlights = {
          prompt = "Highlights❯ ",
        },
        helptags = {
          prompt = "Help❯ ",
        },
        manpages = {
          prompt = "Man❯ ",
        },
        lsp = {
          previewer = false,
          prompt_postfix = "❯ ",
          symbols = {
            file_icons = true,
            color_icons = true,
            symbol_hl_prefix = "CmpItemKind",
          },
          code_actions = {
            prompt = "LSP Code Actions❯ ",
            ui_select = true, -- use 'vim.ui.select'?
            winopts = {
              row = 0.40,
              height = 0.35,
              width = 0.60,
            },
          },
          finder = {
            prompt = "LSP Finder❯ ",
          },
          diagnostics = {
            prompt = "LSP Diagnostics❯ ",
          },
        },
      }
    end,
  },
}
