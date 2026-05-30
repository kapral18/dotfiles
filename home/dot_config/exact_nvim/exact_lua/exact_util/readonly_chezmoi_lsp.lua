--- Redirect LSP location jumps to chezmoi *source* files.
---
--- When this neovim config is edited from its chezmoi source tree
--- (`~/.local/share/chezmoi/home/...`), language servers still resolve symbols
--- against the *deployed* copies under `$HOME` (e.g. lua_ls resolves
--- `require("plugins_local_src.qf")` to `~/.config/nvim/lua/plugins_local_src/qf.lua`).
--- So `gd`/`gr` from inside a source file jump to the rendered target — the very
--- file `chezmoi apply` silently overwrites (AGENTS.md C1: edit `home/**`, never
--- the `$HOME` targets).
---
--- This rewrites LSP location results so that, *only when the originating buffer
--- is itself a chezmoi source file*, any destination that is a chezmoi-managed
--- target is swapped for its source path (`chezmoi source-path <target>`). The
--- line/column are preserved; for non-template sources the content is byte
--- identical so the cursor lands exactly. For `.tmpl` sources the rows may drift
--- but you still land in the correct source file.
---
--- The single chokepoint is `vim.lsp.buf_request{,_sync}`: fzf-lua (this config's
--- jump engine) calls these directly and bypasses `vim.lsp.handlers`, and its
--- `jump1` fast path jumps via `show_document` on the raw location URI — so the
--- URIs must be rewritten at the request boundary, not at item-formatting time.
local M = {}

--- LSP methods whose results carry navigable file locations.
local LOCATION_METHODS = {
  ["textDocument/definition"] = true,
  ["textDocument/declaration"] = true,
  ["textDocument/typeDefinition"] = true,
  ["textDocument/implementation"] = true,
  ["textDocument/references"] = true,
}

--- target absolute path -> source absolute path, or false when not redirectable.
---@type table<string, string|false>
local source_cache = {}

local function home_dir()
  return vim.uv.os_homedir() or os.getenv("HOME") or ""
end

--- True when `path` is `dir` or lives beneath it (both should be realpaths).
---@param path string|nil
---@param dir string|nil
---@return boolean
local function is_under(path, dir)
  if type(path) ~= "string" or type(dir) ~= "string" or dir == "" then
    return false
  end
  path = path:gsub("/+$", "")
  dir = dir:gsub("/+$", "")
  return path == dir or path:sub(1, #dir + 1) == (dir .. "/")
end

--- Resolved root of the chezmoi source tree (set by `plugins/chezmoi.lua`).
---@return string
local function chezmoi_root()
  local root = vim.g["chezmoi#source_dir_path"]
  if type(root) ~= "string" or root == "" then
    root = home_dir() .. "/.local/share/chezmoi"
  end
  return vim.uv.fs_realpath(root) or root
end

--- Is the buffer that issued the request a chezmoi source file?
---@param bufnr integer|nil
---@return boolean
local function is_source_buf(bufnr)
  local name = vim.api.nvim_buf_get_name(bufnr or 0)
  if name == "" then
    return false
  end
  local real = vim.uv.fs_realpath(name) or name
  return is_under(real, chezmoi_root())
end

--- Cheap pre-filter: skip paths that can never be a chezmoi-managed dotfile
--- target (neovim plugins/runtime, anything outside `$HOME`, and source files
--- themselves), so reference lists don't spawn a `chezmoi` probe per result.
---@param fname string
---@return boolean
local function is_resolvable_target(fname)
  if not is_under(fname, home_dir()) then
    return false
  end
  if is_under(fname, vim.fn.stdpath("data")) then
    return false
  end
  local runtime = vim.env.VIMRUNTIME
  if runtime and runtime ~= "" and is_under(fname, runtime) then
    return false
  end
  if is_under(fname, chezmoi_root()) then
    return false
  end
  return true
end

--- Resolve a deployed target to its chezmoi source, cached (incl. negatives).
---@param fname string
---@return string|nil
local function source_for_target(fname)
  local cached = source_cache[fname]
  if cached ~= nil then
    return cached or nil
  end

  local resolved = false
  if is_resolvable_target(fname) then
    local ok, out = pcall(function()
      return vim.system({ "chezmoi", "source-path", fname }, { text = true }):wait()
    end)
    if ok and out and out.code == 0 then
      local src = vim.trim(out.stdout or "")
      if src ~= "" and vim.uv.fs_stat(src) then
        resolved = src
      end
    end
  end

  source_cache[fname] = resolved
  return resolved or nil
end

--- Swap a single location's URI field (`uri` or `targetUri`) to its source.
---@param loc table
---@param key "uri"|"targetUri"
local function rewrite_uri_field(loc, key)
  local uri = loc[key]
  if type(uri) ~= "string" or not vim.startswith(uri, "file://") then
    return
  end
  local src = source_for_target(vim.uri_to_fname(uri))
  if src then
    loc[key] = vim.uri_from_fname(src)
  end
end

--- Rewrite a definition/references result (single Location or a list of
--- Location/LocationLink) in place. Ranges are preserved.
---@generic T
---@param result T
---@return T
local function rewrite_locations(result)
  if type(result) ~= "table" then
    return result
  end

  if result.uri or result.targetUri then
    rewrite_uri_field(result, "uri")
    rewrite_uri_field(result, "targetUri")
    return result
  end

  for _, loc in ipairs(result) do
    if type(loc) == "table" then
      rewrite_uri_field(loc, "uri")
      rewrite_uri_field(loc, "targetUri")
    end
  end
  return result
end

M.rewrite_locations = rewrite_locations

--- Install the request wrappers once. Idempotent.
function M.setup()
  if M._installed then
    return
  end
  M._installed = true

  local orig_sync = vim.lsp.buf_request_sync
  vim.lsp.buf_request_sync = function(bufnr, method, params, timeout)
    local responses = orig_sync(bufnr, method, params, timeout)
    if LOCATION_METHODS[method] and type(responses) == "table" and is_source_buf(bufnr) then
      for _, response in pairs(responses) do
        if type(response) == "table" and response.result then
          response.result = rewrite_locations(response.result)
        end
      end
    end
    return responses
  end

  local orig_async = vim.lsp.buf_request
  vim.lsp.buf_request = function(bufnr, method, params, handler)
    if LOCATION_METHODS[method] and type(handler) == "function" and is_source_buf(bufnr) then
      local user_handler = handler
      handler = function(err, result, ctx, config)
        if result then
          result = rewrite_locations(result)
        end
        return user_handler(err, result, ctx, config)
      end
    end
    return orig_async(bufnr, method, params, handler)
  end
end

return M
