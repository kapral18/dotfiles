local M = {}

--- Get the real path, resolving any symlinks
--- @param p string The path to resolve.
--- @return string The resolved real path, or the original path if resolution fails.
local function realpath(p)
  local ok, rp = pcall(vim.uv.fs_realpath, p)
  ---@cast rp string
  return ok and rp or p
end

local home = vim.uv.os_homedir()
local work_root = realpath(home .. "/work")

--- Check if a given path is inside the work folder
--- @param path string|nil The path to check. If nil, uses the current buffer's path.
--- @return boolean True if the path is inside the work folder, false otherwise.
function M.in_work_dir(path)
  path = path or vim.api.nvim_buf_get_name(0)
  if not path or path == "" then
    return false
  end
  local rp = realpath(path)
  return rp:sub(1, #work_root + 1) == (work_root .. "/")
end

return M
