local M = {}

---@param opts? { force?: boolean }
M.copy_buffer_to_quickfix_dirs = function(opts)
  local options = opts or {}

  local qflist = vim.fn.getqflist()
  if #qflist == 0 then
    vim.notify("Quickfix list is empty", vim.log.levels.WARN)
    return
  end

  local current_buf = vim.api.nvim_get_current_buf()
  local current_file = vim.api.nvim_buf_get_name(current_buf)

  if current_file == "" then
    vim.notify("Current buffer has no filename", vim.log.levels.ERROR)
    return
  end

  local source_filename = vim.fn.fnamemodify(current_file, ":t")
  local source_content = vim.api.nvim_buf_get_lines(current_buf, 0, -1, false)

  local processed_dirs = {}

  for _, entry in ipairs(qflist) do
    local target_file = entry.filename or vim.api.nvim_buf_get_name(entry.bufnr)
    if not target_file or target_file == "" then
      goto continue
    end

    local target_dir = vim.fn.fnamemodify(target_file, ":h")
    if processed_dirs[target_dir] then
      goto continue
    end

    local target_path = target_dir .. "/" .. source_filename

    if vim.fn.filereadable(target_path) == 1 and not options.force then
      vim.notify("Skipping existing file: " .. target_path, vim.log.levels.WARN)
      goto continue
    end

    if vim.fn.isdirectory(target_dir) == 0 then
      local ok, err = pcall(vim.fn.mkdir, target_dir, "p")
      if not ok then
        vim.notify("Failed to create directory: " .. target_dir .. " - " .. err, vim.log.levels.ERROR)
        goto continue
      end
    end

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
