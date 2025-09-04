return {
  {
    "folke/persistence.nvim",
    enabled = false,
  },
  {
    "rmagatti/auto-session",
    lazy = false,
    dependencies = {
      { "nvim-telescope/telescope.nvim", opt = true },
    },
    keys = {
      { "<localleader>ss", "<cmd>SessionSave<CR>", desc = "Save session" },
    },
    ---enables autocomplete for opts
    ---@module "auto-session"
    ---@type AutoSession.Config
    opts = {
      suppressed_dirs = { "~/", "~/code", "~/Downloads", "/" },
      pre_save_cmds = {
        "tabdo Neotree close",
      },
      use_git_branch = true,
      post_restore_cmds = {
        -- spread out loading buffers to avoid lag spikes
        -- and to make them loaded so that copilot-chat can
        -- detect them with #buffers
        function()
          local bufs = vim.api.nvim_list_bufs()
          local chunk_size = 5 -- Load 5 buffers at a time
          local i = 1

          local function load_chunk()
            local count = 0
            while i <= #bufs and count < chunk_size do
              local buf = bufs[i]
              if vim.api.nvim_buf_is_valid(buf) and not vim.api.nvim_buf_is_loaded(buf) then
                local name = vim.api.nvim_buf_get_name(buf)
                if name ~= "" and vim.fn.filereadable(name) == 1 then
                  vim.fn.bufload(buf)
                end
              end
              i = i + 1
              count = count + 1
            end

            -- Schedule next chunk if there are more buffers
            if i <= #bufs then
              vim.defer_fn(load_chunk, 50) -- 50ms delay between chunks
            end
          end

          -- Start loading after a small initial delay
          vim.defer_fn(load_chunk, 100)
        end,
      },
    },
  },
}
