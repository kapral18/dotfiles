return {
  "akinsho/bufferline.nvim",
  version = "*",
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

        local path_to_process

        local sep = package.config:sub(1, 1)
        if path ~= cwd and vim.startswith(path, cwd .. sep) then
          path_to_process = vim.fn.fnamemodify(path, ":.")
        else
          path_to_process = path
        end

        -- Show the filename and up to two parent directories.
        local parts = {}
        local current_part = path_to_process
        local count = 0

        while current_part and current_part ~= "" and current_part ~= "." and current_part ~= sep and count < 3 do
          local basename = vim.fs.basename(current_part)
          -- A trailing separator can leave the first basename empty.
          if basename == "" and #parts == 0 then
            basename = vim.fs.basename(vim.fs.dirname(current_part))
          end

          if basename == "" then
            break
          end

          table.insert(parts, 1, basename)
          local parent = vim.fs.dirname(current_part)

          if parent == current_part then
            break
          end

          current_part = parent
          count = count + 1
        end

        if #parts == 0 then
          return buf.name or vim.fs.basename(path) or "[No Name]"
        end

        return table.concat(parts, sep)
      end,
    },
  },
  init = function()
    vim.keymap.set(
      "n",
      "<A-h>",
      "<cmd>BufferLineCyclePrev<CR>",
      { noremap = true, silent = true, desc = "Previous buffer" }
    )
    vim.keymap.set(
      "n",
      "<A-l>",
      "<cmd>BufferLineCycleNext<CR>",
      { noremap = true, silent = true, desc = "Next buffer" }
    )
  end,
}
