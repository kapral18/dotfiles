local M = {}

-- Constants
local MAX_BUFFERLINE_COMPONENTS = 3
local FALLBACK_DISPLAY = " "

---Get the relative path from current working directory
---@return string|nil relative_path The path relative to CWD, or nil if no path
---@return boolean is_in_cwd Whether the file is within the current working directory
local function get_path_from_cwd()
  local full_path = vim.fn.expand("%:p")
  if full_path == "" then
    return nil, false
  end -- No path

  local cwd = vim.fn.getcwd()
  local path_sep = package.config:sub(1, 1) -- '/' or '\'
  if cwd:sub(-1) ~= path_sep then
    cwd = cwd .. path_sep
  end

  local is_in_cwd = (full_path:find(cwd, 1, true) == 1)
  local relative_path

  if is_in_cwd then
    relative_path = full_path:sub(#cwd + 1)
    if relative_path == "" then
      relative_path = "."
    end -- Is CWD root
  else
    -- Outside CWD: Use path relative to root/drive as default
    relative_path = vim.fn.fnamemodify(full_path, ":.")
    -- Optional: Could fallback to filename if relative-to-root is still absolute
  end
  return relative_path, is_in_cwd
end

---Calculate how many path components bufferline will display
---@param num_total_components integer Total number of path components
---@param is_in_cwd boolean Whether the file is in the current working directory
---@return integer count Number of components that bufferline will show
local function get_bufferline_component_count(num_total_components, is_in_cwd)
  if num_total_components == 0 then
    return 0
  end

  local count = 0
  if is_in_cwd then
    -- Bufferline shows filename + up to 2 parents = max 3 components
    count = math.min(num_total_components, MAX_BUFFERLINE_COMPONENTS)
  else
    -- If outside CWD, assume bufferline shows only filename effectively
    -- Adjust this assumption if your bufferline logic differs for non-CWD files
    count = math.min(num_total_components, 1) -- Just filename assumption
  end
  return count
end

---@class PathInfo
---@field path_components string[] Array of path components split by separator
---@field num_total_components integer Total number of path components
---@field path_sep string Path separator character ('/' or '\')

---Get path information and validate basic conditions
---@return PathInfo|nil path_info Path information object, or nil if invalid
---@return boolean is_in_cwd Whether the file is in the current working directory
local function get_path_info()
  local relative_path, is_in_cwd = get_path_from_cwd()
  if not relative_path or relative_path == "." then
    return nil, is_in_cwd
  end

  local path_sep = package.config:sub(1, 1)
  local path_components = vim.split(relative_path, path_sep, { trimempty = true })
  local num_total_components = #path_components

  if num_total_components == 0 then
    return nil, is_in_cwd
  end

  return {
    path_components = path_components,
    num_total_components = num_total_components,
    path_sep = path_sep,
  },
    is_in_cwd
end

---Extract winbar-specific components (excluding what bufferline will show)
---@param path_info PathInfo Path information object
---@param is_in_cwd boolean Whether the file is in the current working directory
---@return string[] winbar_components Array of path components for winbar display
local function calculate_winbar_components(path_info, is_in_cwd)
  local bufferline_count = get_bufferline_component_count(path_info.num_total_components, is_in_cwd)
  local winbar_end_index = path_info.num_total_components - bufferline_count

  if winbar_end_index <= 0 then
    return {}
  end

  local winbar_components = {}
  for i = 1, winbar_end_index do
    table.insert(winbar_components, path_info.path_components[i])
  end

  return winbar_components
end

---Handle cases where content doesn't fit and needs truncation
---@param available_width integer Available width for display
---@param ellipsis string Ellipsis string to use for truncation
---@param trailing_sep string Trailing separator string
---@return string fallback_content Fallback content that fits within available width
local function handle_truncation_fallback(available_width, ellipsis, trailing_sep)
  local ellipsis_width = vim.fn.strdisplaywidth(ellipsis)
  local trailing_sep_width = vim.fn.strdisplaywidth(trailing_sep)

  if ellipsis_width + trailing_sep_width <= available_width then
    return ellipsis .. trailing_sep
  elseif ellipsis_width <= available_width then
    return ellipsis
  else
    return FALLBACK_DISPLAY
  end
end

---Build truncated content that fits within available space
---@param winbar_components string[] Array of winbar path components
---@param max_content_width integer Maximum width available for content
---@param path_sep string Path separator character
---@return string truncated_content Truncated content string
local function build_truncated_content(winbar_components, max_content_width, path_sep)
  local truncated_content = ""
  local current_content_width = 0

  for i = #winbar_components, 1, -1 do
    local component = winbar_components[i]
    local component_width = vim.fn.strdisplaywidth(component)
    local sep_to_add = (current_content_width > 0) and path_sep or ""
    local sep_width = vim.fn.strdisplaywidth(sep_to_add)

    if component_width + sep_width + current_content_width <= max_content_width then
      truncated_content = component .. sep_to_add .. truncated_content
      current_content_width = current_content_width + component_width + sep_width
    else
      break
    end
  end

  return truncated_content
end

---Format the final winbar path with truncation logic
---@param winbar_components string[] Array of winbar path components
---@param path_info PathInfo Path information object
---@return string formatted_path Final formatted path string for winbar display
local function format_winbar_path(winbar_components, path_info)
  if #winbar_components == 0 then
    return FALLBACK_DISPLAY
  end

  local available_width = vim.fn.winwidth(0)
  local trailing_sep = path_info.path_sep
  local ellipsis = "..."
  local trailing_sep_width = vim.fn.strdisplaywidth(trailing_sep)
  local ellipsis_width = vim.fn.strdisplaywidth(ellipsis)

  if available_width < 1 then
    return FALLBACK_DISPLAY
  end

  -- Check if full content fits without truncation
  local full_winbar_string = table.concat(winbar_components, path_info.path_sep)
  local full_winbar_width = vim.fn.strdisplaywidth(full_winbar_string)

  if full_winbar_width + trailing_sep_width <= available_width then
    return full_winbar_string .. trailing_sep
  end

  -- Handle truncation
  local max_content_width = available_width - ellipsis_width - trailing_sep_width

  if max_content_width < 0 then
    return handle_truncation_fallback(available_width, ellipsis, trailing_sep)
  end

  local truncated_content = build_truncated_content(winbar_components, max_content_width, path_info.path_sep)

  if truncated_content ~= "" then
    return ellipsis .. truncated_content .. trailing_sep
  else
    return handle_truncation_fallback(available_width, ellipsis, trailing_sep)
  end
end

---Get the winbar remainder path (path components not shown in bufferline)
---@return string winbar_path Formatted path string for winbar display
function M.get_winbar_remainder_path()
  local ok, result = pcall(function()
    local path_info, is_in_cwd = get_path_info()
    if not path_info then
      return FALLBACK_DISPLAY
    end

    local winbar_components = calculate_winbar_components(path_info, is_in_cwd)
    return format_winbar_path(winbar_components, path_info)
  end)

  return ok and result or FALLBACK_DISPLAY
end

return M
