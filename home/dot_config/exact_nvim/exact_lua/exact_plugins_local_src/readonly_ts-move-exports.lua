local M = {}

-- LSP client name registered by pmizio/typescript-tools.nvim (config.lua: M.plugin_name).
local TS_CLIENT_NAME = "typescript-tools"

local RENAME_TIMEOUT_MS = 10000
local REFERENCES_TIMEOUT_MS = 10000
-- tsserver "Cannot find name" codes that add-missing-imports fixes (api.lua: MISSING_IMPORT_CODES).
local MISSING_NAME_CODES = { [2304] = true, [2552] = true }
local DIAGNOSTIC_WAIT_MS = 3000
local DIAGNOSTIC_POLL_MS = 50

---@param bufnr integer
---@return vim.lsp.Client|nil
local function get_ts_client(bufnr)
  return vim.lsp.get_clients({ bufnr = bufnr, name = TS_CLIENT_NAME })[1]
end

-- Treesitter capture of every exported binding name inside a 0-indexed row range.
-- Returns name nodes; callers that need stable identity across edits should read
-- the text immediately, not retain the nodes across buffer mutations.
M.query_export_names = function(bufnr, start_row, end_row)
  local parser = vim.treesitter.get_parser(bufnr, "typescript")
  if not parser then
    return {}
  end
  local tree = parser:parse()[1]
  local root = tree:root()

  local query = vim.treesitter.query.parse(
    "typescript",
    [[
    (export_statement
      declaration:[
        (type_alias_declaration
          name: (type_identifier) @export_name)
        (lexical_declaration
          (variable_declarator
            name: (identifier) @export_name))
        (function_declaration
          name: (identifier) @export_name)
        (class_declaration
          name: (type_identifier) @export_name)
        (interface_declaration
          name: (type_identifier) @export_name)
        (enum_declaration
          name: (identifier) @export_name)
      ])
  ]]
  )

  local export_names = {}
  for id, node in query:iter_captures(root, bufnr, start_row, end_row + 1) do
    if query.captures[id] == "export_name" then
      table.insert(export_names, node)
    end
  end
  return export_names
end

-- Files (other than the current one) that reference any export in the range.
-- Positions are 0-indexed to match treesitter node:start() and the LSP spec.
M.get_lsp_references_for_exports = function(bufnr, start_row, end_row)
  local unique_paths = {}
  local current_file = vim.api.nvim_buf_get_name(bufnr)
  local export_nodes = M.query_export_names(bufnr, start_row, end_row)

  local client = get_ts_client(bufnr)
  if not client then
    vim.notify(TS_CLIENT_NAME .. " LSP client not found", vim.log.levels.ERROR)
    return {}
  end

  for _, node in ipairs(export_nodes) do
    local node_row, node_col = node:start()
    local params = {
      textDocument = vim.lsp.util.make_text_document_params(bufnr),
      position = { line = node_row, character = node_col },
      context = { includeDeclaration = false },
    }

    local response = client:request_sync("textDocument/references", params, REFERENCES_TIMEOUT_MS, bufnr)
    if response and response.result then
      for _, ref in ipairs(response.result) do
        if ref and ref.uri then
          local path = vim.uri_to_fname(ref.uri)
          if path ~= current_file then
            unique_paths[path] = true
          end
        end
      end
    end
  end

  return vim.tbl_keys(unique_paths)
end

-- Synchronous LSP rename at a 0-indexed position. Applies the resulting
-- workspace edit across every affected file/buffer.
local function rename_symbol_at(bufnr, row, col, new_name)
  local client = get_ts_client(bufnr)
  if not client then
    vim.notify(TS_CLIENT_NAME .. " LSP client not found", vim.log.levels.ERROR)
    return false
  end

  local params = {
    textDocument = vim.lsp.util.make_text_document_params(bufnr),
    position = { line = row, character = col },
    newName = new_name,
  }

  local response, err = client:request_sync("textDocument/rename", params, RENAME_TIMEOUT_MS, bufnr)
  if err or not response or response.err or not response.result then
    vim.notify("Rename failed: " .. vim.inspect(err or (response and response.err)), vim.log.levels.ERROR)
    return false
  end

  vim.lsp.util.apply_workspace_edit(response.result, client.offset_encoding)
  return true
end

M.generate_unique_name = function(original_name, index)
  return string.format("__tme_moved_%s_%d", original_name, index)
end

-- Open path in the current window with the typescript-tools client attached and
-- diagnostics computed, then run is_sync add-missing-imports and save.
local function add_missing_imports_in_file(path)
  local bufnr = vim.fn.bufadd(path)
  vim.fn.bufload(bufnr)
  vim.api.nvim_win_set_buf(0, bufnr)

  -- Ensure the typescript-tools client is attached before requesting fixes.
  local client = get_ts_client(bufnr)
  if not client then
    vim.cmd("edit") -- triggers FileType/LSP attach for the now-focused buffer
    client = get_ts_client(bufnr)
  end
  if not client then
    vim.notify("No " .. TS_CLIENT_NAME .. " client for " .. path, vim.log.levels.WARN)
    return
  end

  -- add_missing_imports only fixes existing "cannot find name" diagnostics, so
  -- wait until tsserver has published at least one before asking.
  local deadline = vim.loop.now() + DIAGNOSTIC_WAIT_MS
  local function has_missing_name_diagnostic()
    for _, d in ipairs(vim.diagnostic.get(bufnr)) do
      if d.code and MISSING_NAME_CODES[d.code] then
        return true
      end
    end
    return false
  end
  while not has_missing_name_diagnostic() and vim.loop.now() < deadline do
    vim.wait(DIAGNOSTIC_POLL_MS, function()
      return has_missing_name_diagnostic()
    end)
  end

  require("typescript-tools.api").add_missing_imports(true)
  vim.cmd("write")
end

-- Append the selected lines to new_path (creating parent dirs), then delete them
-- from the source buffer. Returns the new buffer (loaded) on success.
local function move_lines_to_new_file(src_bufnr, start_row, end_row, new_path)
  local lines = vim.api.nvim_buf_get_lines(src_bufnr, start_row, end_row + 1, false)

  vim.fn.mkdir(vim.fs.dirname(new_path), "p")

  local existing = {}
  if vim.fn.filereadable(new_path) == 1 then
    existing = vim.fn.readfile(new_path)
    table.insert(existing, "")
  end
  vim.list_extend(existing, lines)

  local ok = pcall(vim.fn.writefile, existing, new_path)
  if not ok then
    vim.notify("Failed to write file: " .. new_path, vim.log.levels.ERROR)
    return nil
  end

  vim.api.nvim_buf_set_lines(src_bufnr, start_row, end_row + 1, false, {})
  vim.api.nvim_buf_call(src_bufnr, function()
    vim.cmd("write")
  end)

  local new_bufnr = vim.fn.bufadd(new_path)
  vim.fn.bufload(new_bufnr)
  return new_bufnr
end

-- Locate a 0-indexed position of an export name in a buffer by treesitter.
local function find_export_position(bufnr, name)
  local nodes = M.query_export_names(bufnr, 0, vim.api.nvim_buf_line_count(bufnr) - 1)
  for _, node in ipairs(nodes) do
    if vim.treesitter.get_node_text(node, bufnr) == name then
      local row, col = node:start()
      return row, col
    end
  end
  return nil
end

M.ts_move_exports = function()
  vim.ui.input({ prompt = "Enter new path: " }, function(input)
    if not input or input == "" then
      vim.notify("Please provide a new path", vim.log.levels.ERROR)
      return
    end

    local src_bufnr = vim.api.nvim_get_current_buf()
    local src_win = vim.api.nvim_get_current_win()
    local new_path = vim.fs.normalize(vim.fs.joinpath(vim.fn.expand("%:p:h"), input))

    local start_row = vim.api.nvim_buf_get_mark(src_bufnr, "<")[1] - 1
    local end_row = vim.api.nvim_buf_get_mark(src_bufnr, ">")[1] - 1

    -- 1. Snapshot export names as strings (nodes go stale after edits).
    local export_nodes = M.query_export_names(src_bufnr, start_row, end_row)
    if #export_nodes == 0 then
      vim.notify("No exported declarations in selection", vim.log.levels.ERROR)
      return
    end
    local original_names = {}
    for _, node in ipairs(export_nodes) do
      table.insert(original_names, vim.treesitter.get_node_text(node, src_bufnr))
    end

    -- 2. Collect referencing files before any edits.
    local reference_paths = M.get_lsp_references_for_exports(src_bufnr, start_row, end_row)

    -- 3. Rename each export to a unique placeholder in the source buffer so that,
    --    once moved, importers surface "cannot find name" diagnostics for it.
    local unique_names = {}
    for i, name in ipairs(original_names) do
      local row, col = find_export_position(src_bufnr, name)
      if row then
        local unique = M.generate_unique_name(name, i)
        if rename_symbol_at(src_bufnr, row, col, unique) then
          unique_names[i] = unique
        else
          unique_names[i] = name
        end
      else
        unique_names[i] = name
      end
    end

    -- 4. Move the selected lines into the new file and load it.
    local new_bufnr = move_lines_to_new_file(src_bufnr, start_row, end_row, new_path)
    if not new_bufnr then
      return
    end

    -- 5. Re-import the (placeholder-named) symbols in each referencing file.
    for _, path in ipairs(reference_paths) do
      add_missing_imports_in_file(path)
    end

    -- 6. Rename placeholders back to their original names from the new file. The
    --    LSP rename propagates through every importer added in step 5.
    vim.api.nvim_win_set_buf(0, new_bufnr)
    for i, original in ipairs(original_names) do
      local unique = unique_names[i]
      if unique ~= original then
        local row, col = find_export_position(new_bufnr, unique)
        if row then
          rename_symbol_at(new_bufnr, row, col, original)
        end
      end
    end
    vim.api.nvim_buf_call(new_bufnr, function()
      vim.cmd("write")
    end)

    -- Restore focus to the original source window.
    if vim.api.nvim_win_is_valid(src_win) then
      vim.api.nvim_set_current_win(src_win)
      vim.api.nvim_win_set_buf(src_win, src_bufnr)
    end

    vim.notify(
      string.format("Moved %d export(s) to %s", #original_names, vim.fn.fnamemodify(new_path, ":~:.")),
      vim.log.levels.INFO
    )
  end)
end

return M
