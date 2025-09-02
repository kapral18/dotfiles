local Util = require("lazyvim.util")

return {
  "akinsho/bufferline.nvim",
  lazy = false,
  opts = {
    options = {
      separator_style = "slant",
      always_show_bufferline = true,
      show_close_icon = false,
      show_buffer_close_icons = false,
      diagnostics = false,
      diagnostics_indicator = nil,
      offsets = {},
      truncate_names = false,
      name_formatter = function(buf)
        local path = buf.path
        if not path or path == "" then
          return buf.name or "[No Name]"
        end

        path = vim.fs.normalize(path)
        local cwd = vim.fs.normalize(vim.fn.getcwd())

        local path_to_process -- This will be the path string we take components from

        -- Check if path is strictly inside cwd (starts with cwd + separator)
        -- Using package.config:sub(1,1) gets the OS-specific path separator ('/' or '\')
        local sep = package.config:sub(1, 1)
        if path ~= cwd and vim.startswith(path, cwd .. sep) then
          -- Path is inside CWD: get the path relative to CWD
          path_to_process = vim.fn.fnamemodify(path, ":.")
        else
          -- Path is outside CWD or *is* CWD: use the absolute path
          path_to_process = path
        end

        -- Now, extract the filename and up to two parent directories from 'path_to_process'
        local parts = {}
        local current_part = path_to_process
        local count = 0

        -- Iteratively get the basename and move to the parent directory, up to 3 times
        while current_part and current_part ~= "" and current_part ~= "." and current_part ~= sep and count < 3 do
          local basename = vim.fs.basename(current_part)
          -- Handle edge case where path might end in a separator, resulting in empty basename initially
          if basename == "" and #parts == 0 then
            basename = vim.fs.basename(vim.fs.dirname(current_part))
          end

          if basename == "" then
            break
          end -- Stop if we can't extract a part

          table.insert(parts, 1, basename) -- Prepend (add to the beginning) the extracted part
          local parent = vim.fs.dirname(current_part)

          -- Stop if dirname didn't change (e.g., reached root "/", ".", or an error)
          if parent == current_part then
            break
          end

          current_part = parent
          count = count + 1
        end

        -- If path_to_process was empty or extraction failed somehow, fallback
        if #parts == 0 then
          -- Use the original buffer name or filename as a last resort
          return buf.name or vim.fs.basename(path) or "[No Name]"
        end

        -- Join the collected parts with the OS-specific separator
        return table.concat(parts, sep)
      end,
    },
  },
  init = function()
    if Util.has("bufferline.nvim") then
      vim.keymap.set(
        "n",
        "<A-h>",
        Util.has("bufferline.nvim") and "<cmd>BufferLineCyclePrev<CR>" or ":bprevious<CR>",
        { noremap = true, silent = true, desc = "Previous buffer" }
      )
      vim.keymap.set(
        "n",
        "<A-l>",
        Util.has("bufferline.nvim") and "<cmd>BufferLineCycleNext<CR>" or ":bnext<CR>",
        { noremap = true, silent = true, desc = "Next buffer" }
      )
    end
  end,
}
