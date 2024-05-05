---@diagnostic disable: missing-fields
local M = {}

M.win_presets = {
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

local rg_ignore_glob =
  "-g '!{node_modules,.next,dist,build,reports,.idea,.vscode,.yarn,.nyc_output,__generated__,reports,storybook-static},*.min.js,*.min.css,junit.xml,bazel-*,data,target,.buildkite,.chromium,.es,.yarn-*}'"
local fd_ignore_glob =
  "-E '{node_modules,.next,dist,build,reports,.idea,.vscode,.yarn,.nyc_output,__generated__,reports,storybook-static}/' -E '{*.min.js,*.min.css,junit.xml,bazel-*,data,target,.buildkite,.chromium,.es,.yarn-*}'"

M.rg_opts_unrestricted =
  "--column --line-number --no-heading --color=always --smart-case --max-columns=512 --hidden --no-ignore -g '!{.git, tsconfig.tsbuildinfo, *.map}'"

M.rg_opts = M.rg_opts_unrestricted .. " " .. rg_ignore_glob

M.fd_opts_unrestricted =
  "--color=never --type f --hidden --no-ignore --follow -E '!{.git, tsconfig.tsbuildinfo, *.map}'"

M.fd_opts = M.fd_opts_unrestricted .. " " .. fd_ignore_glob

M.fzf = function(cmd, opts)
  opts = opts or {}
  return function()
    require("fzf-lua")[cmd](opts)
  end
end

---@type LazySpec
M.spec = {
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
    "neovim/nvim-lspconfig",
    init = function()
      local keys = require("lazyvim.plugins.lsp.keymaps").get()
      keys[#keys + 1] = {
        "gD",
        M.fzf("lsp_declarations", { jump_to_single_result = true, winopts = M.win_presets.large.vertical }),
        desc = "Goto Declarations",
      }
    end,
  },
  {
    "ibhagwan/fzf-lua",
    lazy = false,
    priority = 200,
    dependencies = { "nvim-tree/nvim-web-devicons" },
    keys = {
      {
        "<leader><leader>",
        M.fzf("files", {
          winopts = M.win_presets.medium.vertical,
        }),
        desc = "Files",
      },
      {
        "<leader>i",
        M.fzf("files", {
          fd_opts = M.fd_opts_unrestricted,
          winopts = M.win_presets.medium.vertical,
        }),
        desc = "Files",
      },
      {
        "<leader>gs",
        M.fzf("git_status", {
          winopts = M.win_presets.large.vertical,
        }),
        desc = "Git Status",
      },
      {
        "<leader>gc",
        M.fzf("git_commits", {
          winopts = M.win_presets.large.vertical,
        }),
        desc = "Git Commits",
      },
      {
        "<leader>fr",
        M.fzf("oldfiles", {
          winopts = M.win_presets.medium.vertical,
          cwd_only = true,
        }),
        desc = "Recent Files (Current Session)",
      },
      {
        "<leader>fR",
        M.fzf("oldfiles", {
          winopts = M.win_presets.medium.vertical,
          cwd_only = true,
          include_current_session = false,
        }),
        desc = "Recent Files (All Sessions)",
      },
      {
        "<leader>ss",
        M.fzf("lsp_document_symbols", {
          winopts = M.win_presets.large.vertical,
        }),
        desc = "Document Symbols",
      },
      {
        "<leader>sS",
        M.fzf("lsp_live_workspace_symbols", {
          winopts = M.win_presets.large.vertical,
        }),
        desc = "Workspace Symbols",
      },
      {
        "<leader>/",
        M.fzf("lgrep_curbuf", {
          winopts = M.win_presets.large.vertical,
        }),
        desc = "Grep",
      },
      {
        "<leader>sg",
        M.fzf("live_grep_glob", {
          winopts = M.win_presets.large.vertical,
        }),
        desc = "Grep (excluding .git and node_modules)",
      },
      {
        "<leader>sG",
        M.fzf("live_grep_glob", {
          rg_opts = M.rg_opts_unrestricted,
          winopts = M.win_presets.large.vertical,
        }),
        desc = "Grep (excluding .git)",
      },
      { '<leader>s"', M.fzf("registers", { winopts = M.win_presets.large.vertical }), desc = "Registers" },
      { "<leader>sa", M.fzf("autocmds", { winopts = M.win_presets.large.vertical }), desc = "Auto Commands" },
      { "<leader>sc", M.fzf("command_history", { winopts = M.win_presets.large.vertical }), desc = "Command History" },
      { "<leader>sC", M.fzf("commands", { winopts = M.win_presets.large.vertical }), desc = "Commands" },
      {
        "<leader>sd",
        M.fzf("diagnostics_document", { winopts = M.win_presets.large.vertical }),
        desc = "Document Diagnostics",
      },
      {
        "<leader>sD",
        M.fzf("diagnostics_workspace", { winopts = M.win_presets.large.vertical }),
        desc = "Workspace Diagnostics",
      },
      { "<leader>sh", M.fzf("help_tags", { winopts = M.win_presets.large.vertical }), desc = "Help Pages" },
      {
        "<leader>sH",
        M.fzf("highlights", { winopts = M.win_presets.large.vertical }),
        desc = "Search Highlight Groups",
      },
      { "<leader>sm", M.fzf("marks", { winopts = M.win_presets.large.vertical }), desc = "Marks" },
      { "<leader>sk", M.fzf("keymaps", { winops = M.win_presets.large.vertical }), desc = "Key Maps" },
      { "<leader>sM", M.fzf("man_pages", { winopts = M.win_presets.large.vertical }), desc = "Man Pages" },
      -- { "<leader>so", "<cmd>Telescope vim_options<cr>", desc = "Options" },
      { "<leader>sR", M.fzf("resume", { winopts = M.win_presets.large.vertical }), desc = "Resume Picker List" },
      {
        "<leader>sw",
        M.fzf("grep_cword", { winopts = M.win_presets.large.vertical }),
        desc = "Grep Word (excluding .git and node_modules)",
      },
      {
        "<leader>sw",
        M.fzf("grep_visual", {
          winopts = M.win_presets.large.vertical,
        }),
        mode = "v",
        desc = "Grep Visual (excluding .git and node_modules)",
      },
      {
        "<leader>sW",
        M.fzf("grep_cword", {
          rg_opts = M.rg_opts_unrestricted,
          winopts = M.win_presets.large.vertical,
        }),
        desc = "Grep Word (excluding .git)",
      },
      {
        "<leader>sW",
        M.fzf("grep_visual", {
          rg_opts = M.rg_opts_unrestricted,
          winopts = M.win_presets.large.vertical,
        }),
        mode = "v",
        desc = "Grep Visual (excluding .git)",
      },
      {
        "<leader>uC",
        M.fzf("colorschemes", { winopts = M.win_presets.large.vertical }),
        desc = "Colorscheme with preview",
      },
      {
        "<leader>sb",
        M.fzf("buffers", { winopts = M.win_presets.large.vertical }),
        desc = "Buffers with preview",
      },
    },
    opts = function()
      local actions = require("fzf-lua.actions")
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
        builtin = {
          prompt = "Builtin❯ ",
          extensions = {
            -- neovim terminal only supports `viu` block output
            ["png"] = { "viu" },
            -- by default the filename is added as last argument
            -- if required, use `{file}` for argument positioning
            ["svg"] = { "chafa", "{file}" },
            ["jpg"] = { "viu" },
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
          rg_opts = M.rg_opts,
          fd_opts = M.fd_opts,
          fzf_opts = { ["--ansi"] = false },
          actions = {
            ["ctrl-q"] = actions.file_sel_to_qf,
            ["ctrl-y"] = function(selected)
              print(selected[1])
            end,
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
          rg_opts = M.rg_opts,
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
            ["ctrl-s"] = actions.buf_split,
            ["ctrl-v"] = actions.buf_vsplit,
            ["ctrl-t"] = actions.buf_tabedit,
          },
        },
        blines = {
          prompt = "BLines❯ ",
          actions = {
            ["ctrl-s"] = actions.buf_split,
            ["ctrl-v"] = actions.buf_vsplit,
            ["ctrl-t"] = actions.buf_tabedit,
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
          previewer = "bat",
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
    config = function(_, opts)
      require("fzf-lua").setup(opts)
    end,
  },
}

return M.spec
