local M = {}

local TS_JS_FILETYPES = {
  typescript = true,
  typescriptreact = true,
  javascript = true,
  javascriptreact = true,
}

local function is_ts_js_filetype()
  return TS_JS_FILETYPES[vim.bo.filetype] == true
end

local function is_list(value)
  if vim.islist then
    return vim.islist(value)
  end
  return type(value) == "table" and value[1] ~= nil
end

local function buf_has_method(method)
  local bufnr = vim.api.nvim_get_current_buf()
  for _, client in ipairs(vim.lsp.get_clients({ bufnr = bufnr })) do
    if client and client.supports_method and client:supports_method(method) then
      return true
    end
  end
  return false
end

local function get_position_encoding()
  local bufnr = vim.api.nvim_get_current_buf()
  local clients = vim.lsp.get_clients({ bufnr = bufnr })
  local client = clients and clients[1] or nil
  return client and client.offset_encoding or "utf-16"
end

local function segment_has_test_word(segment)
  if type(segment) ~= "string" or segment == "" then
    return false
  end
  segment = segment:lower()
  -- Treat "word characters" as alphanumeric only (underscore counts as a separator),
  -- so segments like "foo_test.ts" and "__tests__" are matched but "latest" isn't.
  return segment:match("%f[%a%d]tests?%f[^%a%d]") ~= nil
end

local function path_has_test_segment(filename)
  if type(filename) ~= "string" or filename == "" then
    return false
  end
  local normalized = filename:gsub("\\", "/")
  for segment in normalized:gmatch("[^/]+") do
    if segment_has_test_word(segment) then
      return true
    end
  end
  return false
end

local file_line_cache = {}

local function get_file_lines(filename)
  if file_line_cache[filename] ~= nil then
    return file_line_cache[filename]
  end
  local ok, lines = pcall(vim.fn.readfile, filename)
  if not ok then
    lines = nil
  end
  file_line_cache[filename] = lines
  return lines
end

local function is_lnum_inside_import_or_reexport(lines, lnum)
  if type(lines) ~= "table" or type(lnum) ~= "number" then
    return false
  end
  if lnum < 1 or lnum > #lines then
    return false
  end

  local start_line = nil
  local start_kind = nil
  local search_back = math.max(1, lnum - 80)
  for i = lnum, search_back, -1 do
    local line = lines[i] or ""
    if line:match("^%s*import%s") then
      start_line = i
      start_kind = "import"
      break
    end
    if line:match("^%s*export%s+type%s*[%*{]") or line:match("^%s*export%s*[%*{]") then
      start_line = i
      start_kind = "reexport"
      break
    end
  end
  if not start_line then
    return false
  end

  local end_line = nil
  local search_fwd = math.min(#lines, start_line + 120)
  for i = start_line, search_fwd do
    local line = lines[i] or ""
    if line:match(";%s*$") then
      end_line = i
      break
    end
    if line:match("^%s*import%s+['\"][^'\"]+['\"]%s*;?%s*$") then
      end_line = i
      break
    end
    if line:match("%sfrom%s+['\"][^'\"]+['\"]%s*;?%s*$") then
      end_line = i
      break
    end
    if line:match("^%s*import%s+[%w_].*require%s*%(") then
      end_line = i
      break
    end
    if start_kind == "reexport" and line:match("%sfrom%s+['\"][^'\"]+['\"]%s*;?%s*$") then
      end_line = i
      break
    end
  end

  if not end_line then
    return false
  end

  return lnum >= start_line and lnum <= end_line
end

local function get_symbol_definition_lnums()
  local bufnr = vim.api.nvim_get_current_buf()
  local def_lnums_by_file = {}

  local function add_locations(result, client_id)
    if not result then
      return
    end
    local encoding = "utf-16"
    if client_id then
      local client = vim.lsp.get_client_by_id(client_id)
      encoding = (client and client.offset_encoding) or encoding
    end
    local locations = is_list(result) and result or { result }
    local items = vim.lsp.util.locations_to_items(locations, encoding)
    for _, item in ipairs(items) do
      if item and item.filename and item.lnum then
        def_lnums_by_file[item.filename] = def_lnums_by_file[item.filename] or {}
        def_lnums_by_file[item.filename][item.lnum] = true
      end
    end
  end

  local methods = { "textDocument/definition", "textDocument/declaration" }
  for _, method in ipairs(methods) do
    if buf_has_method(method) then
      local encoding = get_position_encoding()
      local ok, params = pcall(vim.lsp.util.make_position_params, 0, encoding)
      if ok and params then
        local responses = vim.lsp.buf_request_sync(bufnr, method, params, 1500)
        if type(responses) == "table" then
          for client_id, response in pairs(responses) do
            if response and response.result then
              add_locations(response.result, client_id)
            end
          end
        end
      end
    end
  end

  return def_lnums_by_file
end

function M.references_all(opts)
  local actions = require("fzf-lua.actions")
  opts = opts or {}
  return require("fzf-lua").lsp_references(vim.tbl_deep_extend("force", {
    fzf_opts = { ["--multi"] = true },
    actions = {
      ["ctrl-q"] = actions.file_sel_to_qf,
    },
  }, opts))
end

function M.references_smart(opts)
  if not is_ts_js_filetype() then
    return M.references_all(opts)
  end

  opts = opts or {}
  if opts.includeDeclaration == nil then
    opts.includeDeclaration = false
  end

  local current_file = vim.api.nvim_buf_get_name(0)
  local current_file_real = nil
  if type(current_file) == "string" and current_file ~= "" then
    current_file_real = (vim.uv and vim.uv.fs_realpath and vim.uv.fs_realpath(current_file)) or current_file
  end

  local definition_lnums_by_file = get_symbol_definition_lnums()

  return M.references_all(vim.tbl_extend("force", opts, {
    regex_filter = function(item, _)
      if not item or type(item.filename) ~= "string" or type(item.lnum) ~= "number" then
        return true
      end

      -- Never filter references from the current buffer's file. The "smart" filters below
      -- (definition line, import/re-export blocks, test-path heuristics) can hide legit
      -- intra-file references.
      if current_file_real ~= nil then
        local item_real = (vim.uv and vim.uv.fs_realpath and vim.uv.fs_realpath(item.filename)) or item.filename
        if item_real == current_file_real then
          return true
        end
      end

      if definition_lnums_by_file[item.filename] and definition_lnums_by_file[item.filename][item.lnum] then
        return false
      end

      if path_has_test_segment(item.filename) then
        return false
      end

      local lines = get_file_lines(item.filename)
      if is_lnum_inside_import_or_reexport(lines, item.lnum) then
        return false
      end

      return true
    end,
  }))
end

return M
