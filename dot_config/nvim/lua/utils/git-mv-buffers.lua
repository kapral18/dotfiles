local common_utils = require("utils.common")
-- mostly copied from https://github.com/nvim-neo-tree/neo-tree.nvim/blob/230ff118613fa07138ba579b89d13ec2201530b9/lua/neo-tree/sources/filesystem/lib/fs_actions.lua

local M = {}

-- get id of the window to the right of the current one
-- for example, helpful for detecting the win to the right of file explorer
M.get_window_to_right = function()
  local cur_win = vim.api.nvim_get_current_win()
  local cur_win_col = vim.api.nvim_win_get_position(cur_win)[2]
  local wins = vim.api.nvim_tabpage_list_wins(0)
  for _, win in ipairs(wins) do
    local win_col = vim.api.nvim_win_get_position(win)[2]
    if win_col > cur_win_col then
      return win
    end
  end
  return nil
end

---Normalize a path, to avoid errors when comparing paths.
---@param path string The path to be normalize.
---@return string string The normalized path.
M.normalize_path = function(path)
  if M.is_windows then
    -- normalize the drive letter to uppercase
    path = path:sub(1, 1):upper() .. path:sub(2)
  end
  return path
end

---Evaluate the truthiness of a value, according to js/python rules.
---@param value any
---@return boolean
M.truthy = function(value)
  if value == nil then
    return false
  end
  if type(value) == "boolean" then
    return value
  end
  if type(value) == "string" then
    return value > ""
  end
  if type(value) == "number" then
    return value > 0
  end
  if type(value) == "table" then
    return #vim.tbl_values(value) > 0
  end
  return true
end

---Check if a path is a subpath of another.
--@param base string The base path.
--@param path string The path to check is a subpath.
--@return boolean boolean True if it is a subpath, false otherwise.
M.is_subpath = function(base, path)
  if not M.truthy(base) or not M.truthy(path) then
    return false
  elseif base == path then
    return true
  end
  base = M.normalize_path(base)
  path = M.normalize_path(path)
  return string.sub(path, 1, string.len(base)) == base
end

---Opens new_buf in each window that has old_buf currently open.
---Useful during file rename.
---@param old_buf number
---@param new_buf number
M.replace_buffer_in_windows = function(old_buf, new_buf)
  for _, win in ipairs(vim.api.nvim_list_wins()) do
    if vim.api.nvim_win_is_valid(win) and vim.api.nvim_win_get_buf(win) == old_buf then
      vim.api.nvim_win_set_buf(win, new_buf)
    end
  end
end

-- This function renames a buffer in Neovim.
---@param old_path string
---@param new_path string
M.rename_buffer = function(old_path, new_path)
  -- This is a helper function that saves the current buffer.
  local force_save = function()
    vim.cmd("silent! write!")
  end

  -- This loop iterates over all loaded buffers.
  for _, buf in pairs(vim.api.nvim_list_bufs()) do
    -- This condition checks if the buffer is loaded.
    if vim.api.nvim_buf_is_loaded(buf) then
      -- This line gets the name of the current buffer.
      local buf_name = vim.api.nvim_buf_get_name(buf)
      -- This variable will hold the new name of the buffer.
      local new_buf_name = nil
      -- This condition checks if the old path matches the buffer name.
      if old_path == buf_name then
        -- If it does, the new buffer name is set to the new path.
        new_buf_name = new_path
      -- This condition checks if the old path is a subpath of the buffer name.
      elseif M.is_subpath(old_path, buf_name) then
        -- If it is, the new buffer name is set to the new path plus the remaining part of the buffer name.
        new_buf_name = new_path .. buf_name:sub(#old_path + 1)
      end
      -- This condition checks if the new buffer name has been set.
      if M.truthy(new_buf_name) then
        -- If it has, a new buffer is created with the new buffer name.
        local new_buf = vim.fn.bufadd(new_buf_name)

        if new_buf == nil or new_buf == 0 then
          -- If the new buffer couldn't be created, a warning message is displayed.
          vim.cmd("echohl WarningMsg")
          vim.cmd("echo 'Failed to rename buffer: " .. buf_name .. " -> " .. new_buf_name .. "'")
          vim.cmd("echohl NONE")
          return
        end

        -- The new buffer is loaded.
        vim.fn.bufload(new_buf)
        -- The 'buflisted' option for the new buffer is set to true.
        vim.api.nvim_set_option_value("buflisted", true, { buf = new_buf })
        -- The old buffer is replaced with the new buffer in all windows where it's displayed.
        M.replace_buffer_in_windows(buf, new_buf)

        -- This condition checks if the old buffer is not a special buffer.
        if vim.api.nvim_get_option_value("buftype", { buf = buf }) == "" then
          -- This condition checks if the old buffer has been modified.
          local modified = vim.api.nvim_get_option_value("modified", { buf = buf })
          if modified then
            -- If it has, the lines from the old buffer are copied to the new buffer.
            local old_buffer_lines = vim.api.nvim_buf_get_lines(buf, 0, -1, false)
            vim.api.nvim_buf_set_lines(new_buf, 0, -1, false, old_buffer_lines)

            -- A confirmation message is displayed to the user.
            local msg = buf_name .. " has been modified. Save under new name? (y/n) "
            common_utils.confirm(msg, function(confirmed)
              if confirmed then
                -- If the user confirms, the new buffer is saved.
                vim.api.nvim_buf_call(new_buf, force_save)
              else
                -- If the user doesn't confirm, a warning message is displayed.
                vim.cmd("echohl WarningMsg")
                vim.cmd(
                  [[echo "Skipping force save. You'll need to save it with `:w!` when you are ready to force writing with the new name."]]
                )
                vim.cmd("echohl NONE")
              end
            end)
          end
        end
        -- The old buffer is deleted.
        vim.api.nvim_buf_delete(buf, { force = true })
      end
    end
  end
end

return M
