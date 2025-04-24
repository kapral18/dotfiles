local M = {}

-- show confirm input
--@param message string
--@param callback function
M.confirm = function(message, callback)
  local opts = {
    prompt = message .. " y/n: ",
  }
  vim.ui.input(opts, function(value)
    callback(value == "y" or value == "Y")
  end)
end

function M.get_visual()
  local start_pos = vim.fn.getpos("v")
  local end_pos = vim.fn.getpos(".")

  if start_pos == nil or end_pos == nil then
    return ""
  end

  local start_row, start_col = start_pos[2], start_pos[3]
  local end_row, end_col = end_pos[2], end_pos[3]

  if end_row < start_row then
    start_row, end_row = end_row, start_row
  end
  if end_col < start_col then
    start_col, end_col = end_col, start_col
  end

  local lines = vim.api.nvim_buf_get_text(0, start_row - 1, start_col - 1, end_row - 1, end_col, {})

  return table.concat(lines, "\n"), start_row, end_row
end

function M.in_visual()
  local modes = {
    Rv = true,
    Rvc = true,
    Rvx = true,
    V = true,
    Vs = true,
    niV = true,
    noV = true,
    nov = true,
    v = true,
    vs = true,
  }
  local current_mode = vim.api.nvim_get_mode()["mode"]
  return modes[current_mode]
end

function M.copy_to_clipboard(text)
  -- Use pbcopy to copy text to the system clipboard
  local handle = io.popen("pbcopy", "w")
  if handle == nil then
    return
  end
  handle:write(text)
  handle:close()
end

function M.is_image(file_path)
  -- Use a library or a simple heuristic to detect images
  -- For example, you can use the `file` command to check the file type
  local file_type = io.popen("file -b --mime-type " .. vim.fn.shellescape(file_path)):read("*a")
  return file_type:match("image/%w+")
end

function M.open_image(img_path, fallback)
  if M.is_image(img_path) then
    -- Open the image file with the default Mac associated application
    io.popen("open " .. vim.fn.shellescape(img_path))
  else
    -- Handle non-image files as needed
    fallback()
  end
end

return M
