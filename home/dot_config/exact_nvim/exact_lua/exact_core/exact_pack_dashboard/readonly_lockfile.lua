local M = {}

-- Path to the lockfile that `vim.pack` already maintains. Discovered from the
-- 0.12 runtime: `stdpath('config') .. '/nvim-pack-lock.json'`. Exposed so the
-- export/import commands agree with the upstream location.
function M.path()
  return vim.fs.joinpath(vim.fn.stdpath("config"), "nvim-pack-lock.json")
end

-- Copy the live lockfile to `destination`. Parent directory is created if
-- missing. Returns `ok, err_or_path`.
function M.export(destination)
  if type(destination) ~= "string" or destination == "" then
    return false, "destination path is required"
  end

  local expanded = vim.fn.expand(destination)
  if vim.fn.isdirectory(expanded) == 1 then
    expanded = vim.fs.joinpath(expanded, "nvim-pack-lock.json")
  end

  local src = M.path()
  if vim.fn.filereadable(src) ~= 1 then
    return false, "lockfile does not exist yet: " .. src
  end

  local parent = vim.fs.dirname(expanded)
  if parent and parent ~= "" and vim.fn.isdirectory(parent) ~= 1 then
    pcall(vim.fn.mkdir, parent, "p")
  end

  local ok_read, lines = pcall(vim.fn.readfile, src, "b")
  if not ok_read or type(lines) ~= "table" then
    return false, "failed to read lockfile"
  end
  local ok_write, err = pcall(vim.fn.writefile, lines, expanded, "b")
  if not ok_write then
    return false, tostring(err or "failed to write lockfile")
  end

  return true, expanded
end

-- Copy a lockfile from `source` on top of the live lockfile. Validates JSON
-- schema before overwriting. Returns `ok, err_or_path`.
function M.import(source)
  if type(source) ~= "string" or source == "" then
    return false, "source path is required"
  end

  local expanded = vim.fn.expand(source)
  if vim.fn.isdirectory(expanded) == 1 then
    expanded = vim.fs.joinpath(expanded, "nvim-pack-lock.json")
  end
  if vim.fn.filereadable(expanded) ~= 1 then
    return false, "source lockfile not readable: " .. expanded
  end

  local ok_read, lines = pcall(vim.fn.readfile, expanded, "b")
  if not ok_read or type(lines) ~= "table" or #lines == 0 then
    return false, "failed to read source lockfile"
  end

  local ok_decode, decoded = pcall(vim.json.decode, table.concat(lines, "\n"))
  if not ok_decode or type(decoded) ~= "table" or type(decoded.plugins) ~= "table" then
    return false, "source file does not match the vim.pack lockfile schema"
  end

  local dest = M.path()
  local parent = vim.fs.dirname(dest)
  if parent and parent ~= "" and vim.fn.isdirectory(parent) ~= 1 then
    pcall(vim.fn.mkdir, parent, "p")
  end
  local ok_write, err = pcall(vim.fn.writefile, lines, dest, "b")
  if not ok_write then
    return false, tostring(err or "failed to write lockfile")
  end

  return true, dest
end

return M
