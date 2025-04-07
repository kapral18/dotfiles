local test_patterns = {
  test = {
    "%.test%.",
    "%.spec%.",
    "_test%.",
    "_spec%.",
  },
  separator = ".",
  extensions = {
    ts = { "tsx", "js", "jsx" },
    tsx = { "ts", "jsx", "js" },
    js = { "jsx", "ts", "tsx" },
    jsx = { "js", "tsx", "ts" },
    -- Add other extension mappings as needed
  },
}

local function is_test_file(current_file)
  for _, pattern in ipairs(test_patterns.test) do
    if current_file:find(pattern) then
      return true
    end
  end
  return false
end

local function get_alternate_file(current_file)
  local ext = vim.fn.expand("%:e")
  local base_file = current_file:match("(.+)%." .. ext .. "$")

  if is_test_file(current_file) then
    local source_file = current_file
    for _, pattern in ipairs(test_patterns.test) do
      source_file = source_file:gsub(pattern, test_patterns.separator)
    end

    if vim.fn.filereadable(source_file) == 1 then
      return source_file
    else
      -- Check alternate extensions for the source file
      local current_ext = ext
      local alternates = test_patterns.extensions[current_ext]
      if alternates then
        local base_name = source_file:gsub("%." .. current_ext .. "$", "")
        for _, alt_ext in ipairs(alternates) do
          local alt_source = base_name .. "." .. alt_ext
          if vim.fn.filereadable(alt_source) == 1 then
            return alt_source
          end
        end
      end
    end
  else
    -- Generate potential test files with the same extension
    local potential_files = {}
    for _, pattern in ipairs(test_patterns.test) do
      table.insert(potential_files, base_file .. pattern:gsub("%%", "") .. ext)
    end

    -- Check existing files with the same extension
    for _, file in ipairs(potential_files) do
      if vim.fn.filereadable(file) == 1 then
        return file
      end
    end

    -- Generate potential test files with alternate extensions
    local alternates = test_patterns.extensions[ext]
    if alternates then
      for _, alt_ext in ipairs(alternates) do
        for _, pattern in ipairs(test_patterns.test) do
          local alt_file = base_file .. pattern:gsub("%%", "") .. alt_ext
          if vim.fn.filereadable(alt_file) == 1 then
            return alt_file
          end
        end
      end
    end
  end

  return nil
end

local M = {}

function M.switch_src_test()
  local current_file = vim.fn.expand("%:p")
  local alternate_file = get_alternate_file(current_file)

  if alternate_file then
    vim.cmd("edit " .. alternate_file)
  else
    vim.notify(is_test_file(current_file) and "Source file not found" or "Test file not found", vim.log.levels.WARN)
  end
end

return M
