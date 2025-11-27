return {
  {
    "github/copilot.vim",
    -- otherwise for some reason it loads too late and doesn't work
    lazy = false,
    version = "*",
    init = function()
      vim.api.nvim_set_hl(0, "CopilotSuggestion", { fg = "#83a598" })
      vim.api.nvim_set_hl(0, "CopilotAnnotation", { fg = "#03a598" })
    end,
  },
  {
    "CopilotC-Nvim/CopilotChat.nvim",
    lazy = true,
    version = "*",
    cmd = "CopilotChat",
    opts = function()
      local user = vim.env.USER or "User"
      user = user:sub(1, 1):upper() .. user:sub(2)
      return {
        auto_insert_mode = true,
        question_header = "  " .. user .. " ",
        answer_header = "  Copilot ",
        window = { width = 0.4 },
        model = "claude-sonnet-4.5",
      }
    end,
    keys = {
      { "<c-s>", "<CR>", ft = "copilot-chat", desc = "Submit Prompt", remap = true },
      { "<leader>a", "", desc = "+ai", mode = { "n", "v" } },
      {
        "<leader>aa",
        function()
          return require("CopilotChat").toggle()
        end,
        desc = "Toggle (CopilotChat)",
        mode = { "n", "v" },
      },
      {
        "<leader>ax",
        function()
          return require("CopilotChat").reset()
        end,
        desc = "Clear (CopilotChat)",
        mode = { "n", "v" },
      },
      {
        "<leader>ast",
        function()
          return require("CopilotChat").stop()
        end,
        desc = "Stop (CopilotChat)",
        mode = { "n", "v" },
      },
      {
        "<leader>aq",
        function()
          vim.ui.input({ prompt = "Quick Chat:" }, function(input)
            if input ~= "" then
              require("CopilotChat").ask(input)
            end
          end)
        end,
        desc = "Quick Chat (CopilotChat)",
        mode = { "n", "v" },
      },
      {
        "<leader>ap",
        function()
          require("CopilotChat").select_prompt()
        end,
        desc = "Prompt Actions (CopilotChat)",
        mode = { "n", "v" },
      },
    },
    config = function(_, opts)
      local chat = require("CopilotChat")

      -- Function to preload buffers for copilot-chat context
      local function preload_buffers_for_chat()
        local bufs = vim.api.nvim_list_bufs()
        local chunk_size = 3 -- Load 3 buffers at a time
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
      end

      vim.api.nvim_create_autocmd("BufEnter", {
        pattern = "copilot-chat",
        callback = function()
          vim.opt_local.relativenumber = false
          vim.opt_local.number = false
          -- Preload buffers when entering copilot-chat so it can detect them with #buffers
          preload_buffers_for_chat()
        end,
      })

      chat.setup(opts)
    end,
  },
}
