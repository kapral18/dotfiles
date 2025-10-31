--- Get the real path, resolving any symlinks
--- @param p string The path to resolve.
--- @return string The resolved real path, or the original path if resolution fails.
local function realpath(p)
  local ok, rp = pcall(vim.uv.fs_realpath, p)
  ---@cast rp string
  return ok and rp or p
end

--- Check if a given path is inside the work folder
--- @param path string|nil The path to check. If nil, uses the current buffer's path.
--- @return boolean True if the path is inside the work folder, false otherwise.
local function in_work_dir(path)
  local home = vim.uv.os_homedir()
  local work_root = realpath(home .. "/work")
  path = path or vim.api.nvim_buf_get_name(0)
  if not path or path == "" then
    return false
  end
  local rp = realpath(path)
  return rp:sub(1, #work_root + 1) == (work_root .. "/")
end

local is_work_machine = vim.fn.filereadable(vim.fn.expand("~/work/.gitconfig")) == 0

return {
  {
    "github/copilot.vim",
    event = "InsertEnter",
    version = "*",
    init = function()
      vim.api.nvim_set_hl(0, "CopilotSuggestion", { fg = "#83a598" })
      vim.api.nvim_set_hl(0, "CopilotAnnotation", { fg = "#03a598" })

      local function apply(buf)
        local path = vim.api.nvim_buf_get_name(buf)
        local work_ctx = is_work_machine or in_work_dir(path)

        -- Per-buffer Copilot control
        vim.b[buf].copilot_enabled = work_ctx and true or false

        -- Use Copilot's buffer-local disable mechanism
        if work_ctx then
          vim.b[buf].copilot_disabled = false
        else
          vim.b[buf].copilot_disabled = true
        end

        if is_work_machine then
          vim.b[buf].codeium_enabled = false
        else
          vim.b[buf].codeium_enabled = not work_ctx
        end
      end

      vim.api.nvim_create_autocmd({ "BufReadPost", "BufWinEnter", "BufEnter" }, {
        callback = function(args)
          apply(args.buf)
        end,
      })
    end,
  },
  {
    -- we use the Vim version because the Neovim port is still stabilising
    "Exafunction/windsurf.vim",
    event = "InsertEnter",
    init = function()
      vim.g.codeium_disable_bindings = 1
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
          if vim.b.copilot_enabled then
            return require("CopilotChat").toggle()
          else
            vim.notify("CopilotChat is disabled in this buffer", vim.log.levels.WARN)
          end
        end,
        desc = "Toggle (CopilotChat)",
        mode = { "n", "v" },
      },
      {
        "<leader>ax",
        function()
          if vim.b.copilot_enabled then
            return require("CopilotChat").reset()
          else
            vim.notify("CopilotChat is disabled in this buffer", vim.log.levels.WARN)
          end
        end,
        desc = "Clear (CopilotChat)",
        mode = { "n", "v" },
      },
      {
        "<leader>ast",
        function()
          if vim.b.copilot_enabled then
            return require("CopilotChat").stop()
          else
            vim.notify("CopilotChat is disabled in this buffer", vim.log.levels.WARN)
          end
        end,
        desc = "Stop (CopilotChat)",
        mode = { "n", "v" },
      },
      {
        "<leader>aq",
        function()
          if vim.b.copilot_enabled then
            vim.ui.input({ prompt = "Quick Chat:" }, function(input)
              if input ~= "" then
                require("CopilotChat").ask(input)
              end
            end)
          else
            vim.notify("CopilotChat is disabled in this buffer", vim.log.levels.WARN)
          end
        end,
        desc = "Quick Chat (CopilotChat)",
        mode = { "n", "v" },
      },
      {
        "<leader>ap",
        function()
          if vim.b.copilot_enabled then
            require("CopilotChat").select_prompt()
          else
            vim.notify("CopilotChat is disabled in this buffer", vim.log.levels.WARN)
          end
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
