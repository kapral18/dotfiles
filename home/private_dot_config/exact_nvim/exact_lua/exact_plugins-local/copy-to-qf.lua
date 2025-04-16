local M = {}
M.copy_buffer_to_quickfix_dirs = function()
  local current_buf = vim.api.nvim_get_current_buf()
  local current_file = vim.api.nvim_buf_get_name(current_buf)

  -- Validate current buffer has a filename
  if current_file == "" then
    vim.notify("Current buffer has no filename", vim.log.levels.ERROR)
    return
  end

  -- Get source filename components
  local source_filename = vim.fn.fnamemodify(current_file, ":t")
  local source_content = vim.api.nvim_buf_get_lines(current_buf, 0, -1, false)

  -- Process quickfix list
  local qflist = vim.fn.getqflist()
  local processed_dirs = {}

  for _, entry in ipairs(qflist) do
    -- Get target directory from quickfix entry
    local target_file = entry.filename or vim.api.nvim_buf_get_name(entry.bufnr)
    if not target_file or target_file == "" then
      goto continue
    end

    local target_dir = vim.fn.fnamemodify(target_file, ":h")
    if processed_dirs[target_dir] then
      goto continue
    end

    -- Create target path with original filename
    local target_path = target_dir .. "/" .. source_filename

    -- Skip existing files unless force flag is set
    if vim.fn.filereadable(target_path) == 1 then
      vim.notify("Skipping existing file: " .. target_path, vim.log.levels.WARN)
      goto continue
    end

    -- Ensure target directory exists
    if vim.fn.isdirectory(target_dir) == 0 then
      vim.fn.mkdir(target_dir, "p")
    end

    -- Write file contents
    local ok, err = pcall(vim.fn.writefile, source_content, target_path)
    if ok then
      vim.notify("Copied to: " .. target_path, vim.log.levels.INFO)
      processed_dirs[target_dir] = true
    else
      vim.notify("Failed to copy: " .. target_path .. " - " .. err, vim.log.levels.ERROR)
    end

    ::continue::
  end
end

return M
