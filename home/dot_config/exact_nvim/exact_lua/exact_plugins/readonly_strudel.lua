-- Original idea credits: https://github.com/Trevato/nvim/blob/main/lua/plugins/music.lua

-- Music and live coding plugins
-- Only load when NVIM_MUSIC environment variable is set
-- Usage: NVIM_MUSIC=1 nvim or use alias: nvim-music
--
-- Setup:
-- 1. Custom filetype `strdl` for Strudel buffers
-- 2. Treesitter uses JavaScript grammar for Strudel files
-- 3. Strudel.nvim handles browser sync and live coding session

-- Strudel uses custom filetype `strdl` but reuses JavaScript syntax highlighting
vim.filetype.add({
  extension = {
    str = "strdl",
    strdl = "strdl",
    strudel = "strdl",
  },
})

-- Use JavaScript treesitter for strdl filetype
vim.treesitter.language.register("javascript", "strdl")

local music_mode = vim.env.NVIM_MUSIC ~= nil

if music_mode then
  vim.notify("Music mode enabled - Strudel plugin loading", vim.log.levels.INFO)
end

return {
  -- Strudel: Live coding music environment
  {
    "gruvw/strudel.nvim",
    build = "npm install",
    dependencies = { "nvim-treesitter/nvim-treesitter" },
    cond = function()
      return music_mode
    end,
    ft = { "strdl" }, -- Lazy-load when our filetype is detected
    cmd = {
      "StrudelLaunch",
      "StrudelToggle",
      "StrudelUpdate",
      "StrudelQuit",
      "StrudelStop",
      "StrudelExecute",
    },
    -- Lazy-loaded keymaps
    keys = function()
      -- Define configs once for reuse
      local base_config = {
        update_on_save = true,
        report_eval_errors = true,
        browser_data_dir = vim.fn.expand("~/.cache/strudel-nvim/"),
      }

      local headless_config = vim.tbl_deep_extend("force", base_config, {
        headless = true,
        sync_cursor = false,
        ui = {
          hide_code_editor = true,
          hide_menu_panel = false,
          maximise_menu_panel = false,
          hide_top_bar = false,
          hide_error_display = false,
        },
      })

      local visual_config = vim.tbl_deep_extend("force", base_config, {
        headless = false,
        sync_cursor = true,
        ui = {
          hide_code_editor = false, -- Show Strudel code editor for side-by-side
          hide_menu_panel = false,
          maximise_menu_panel = false,
          hide_top_bar = false,
          hide_error_display = false,
        },
      })

      local hydra_config = vim.tbl_deep_extend("force", base_config, {
        headless = false,
        sync_cursor = true,
        report_eval_errors = false,
        ui = {
          hide_code_editor = true,
          hide_menu_panel = true,
          hide_top_bar = true,
          hide_error_display = true,
        },
      })

      return {
        {
          "<leader>ms",
          function()
            require("strudel").setup(headless_config)
            vim.cmd([[StrudelLaunch]])
            vim.defer_fn(function()
              vim.cmd([[StrudelToggle]])
              vim.notify("Strudel headless mode - playing!", vim.log.levels.INFO)
            end, 2000)
          end,
          desc = "Strudel: Start session (headless + auto-play)",
        },
        {
          "<leader>mS",
          function()
            require("strudel").setup(visual_config)
            vim.cmd([[StrudelLaunch]])
            vim.defer_fn(function()
              vim.cmd([[StrudelToggle]])
              vim.notify("Strudel visual mode - playing!", vim.log.levels.INFO)
            end, 2000)
          end,
          desc = "Strudel: Start session (visible + auto-play)",
        },
        {
          "<leader>mH",
          function()
            require("strudel").setup(hydra_config)
            vim.cmd([[StrudelLaunch]])
            vim.defer_fn(function()
              vim.cmd([[StrudelToggle]])
              vim.notify("Strudel Hydra visuals - playing!", vim.log.levels.INFO)
            end, 2000)
          end,
          desc = "Strudel: Start Hydra visuals (auto-play)",
        },
        { "<leader>mt", "<cmd>StrudelToggle<cr>", desc = "Strudel: Toggle playback" },
        { "<leader>mu", "<cmd>StrudelUpdate<cr>", desc = "Strudel: Update/evaluate code" },
        { "<leader>mq", "<cmd>StrudelQuit<cr>", desc = "Strudel: Quit session" },
        { "<leader>mx", "<cmd>StrudelStop<cr>", desc = "Strudel: Stop playback" },
        { "<leader>me", "<cmd>StrudelExecute<cr>", desc = "Strudel: Execute buffer" },
        {
          "<leader>mh",
          function()
            vim.cmd([[StrudelExecute]])
            vim.notify("Executed current buffer in Strudel", vim.log.levels.INFO)
          end,
          desc = "Strudel: Execute and show visuals",
        },
      }
    end,

    -- Use opts instead of config for simple setup
    opts = {
      -- Performance optimizations
      headless = true, -- Reduce GPU/display overhead
      sync_cursor = false, -- Less synchronization overhead
      update_on_save = true, -- Auto-update when saving
      report_eval_errors = true, -- Show errors in Neovim

      -- Browser configuration
      browser_data_dir = vim.fn.expand("~/.cache/strudel-nvim/"),
      browser_exec_path = nil, -- Use system Chromium

      -- UI customization (hide redundant elements)
      ui = {
        hide_code_editor = true, -- We're using Neovim
        hide_menu_panel = false, -- Keep controls visible
        maximise_menu_panel = false, -- Normal size
        hide_top_bar = false, -- Keep navigation
        hide_error_display = false, -- Show errors in browser too
      },

      -- Custom CSS for better integration
      custom_css_file = nil, -- Add custom styling if needed
    },
    -- Setup plugin and autocmds
    config = function(_, opts)
      -- Setup the plugin
      require("strudel").setup(opts)

      -- Auto-commands for Strudel files
      local strudel_group = vim.api.nvim_create_augroup("StrudelMusic", { clear = true })

      -- Remove Strudel's default filetype autocmd (sets to javascript)
      pcall(vim.api.nvim_clear_autocmds, {
        group = "StrudelSync",
        event = { "BufRead", "BufNewFile" },
      })

      -- Ensure filetype remains `strdl` while using JavaScript syntax
      vim.api.nvim_create_autocmd({ "BufReadPost", "FileType" }, {
        group = strudel_group,
        pattern = { "*.str", "*.strdl", "*.strudel", "javascript" },
        callback = function(args)
          local buf = args.buf
          local name = vim.api.nvim_buf_get_name(buf)
          if name:match("%.str$") or name:match("%.strdl$") or name:match("%.strudel$") then
            vim.schedule(function()
              vim.api.nvim_set_option_value("filetype", "strdl", { buf = buf })
              vim.api.nvim_set_option_value("syntax", "javascript", { buf = buf })
              vim.api.nvim_buf_set_var(buf, "strudel_filetype_adjusted", true)
            end)
          end
        end,
      })

      -- Notify on file open (matches all extensions from filetype detection)
      vim.api.nvim_create_autocmd("BufReadPost", {
        group = strudel_group,
        pattern = { "*.str", "*.strdl", "*.strudel" },
        callback = function()
          vim.notify("Strudel file detected. Use <leader>ms to launch browser sync", vim.log.levels.INFO)
          -- Don't auto-launch to avoid unexpected browser windows
          -- User can launch with <leader>ms when ready
        end,
      })

      -- Auto-update on save with visual feedback
      vim.api.nvim_create_autocmd("BufWritePost", {
        group = strudel_group,
        pattern = { "*.str", "*.strdl", "*.strudel" },
        callback = function()
          if vim.g.strudel_launched then
            vim.notify("Strudel pattern updated", vim.log.levels.INFO)
          end
        end,
      })

      -- Ensure Strudel session exits when Neovim closes
      vim.api.nvim_create_autocmd("VimLeavePre", {
        group = strudel_group,
        callback = function()
          pcall(vim.cmd, "StrudelQuit")
        end,
      })
    end,
  },
}
