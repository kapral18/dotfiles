local exists, ts_tools_api = pcall(require, "typescript-tools.api")

if not exists then
  return
end

local M = {}

M.query_export_names = function(bufnr, start_row, end_row)
  local parser = vim.treesitter.get_parser(bufnr, "typescript")
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
      ])
  ]]
  )

  local export_names = {}
  for _, match, _ in query:iter_matches(root, bufnr, start_row, end_row + 1) do
    for id, node in pairs(match) do
      if query.captures[id] == "export_name" then
        table.insert(export_names, node)
      end
    end
  end
  return export_names
end

M.get_lsp_references_for_exports = function(start_row, end_row)
  local unique_paths = {}
  local bufnr = vim.api.nvim_get_current_buf()
  local export_nodes = M.query_export_names(bufnr, start_row, end_row)

  for _, node in ipairs(export_nodes) do
    local node_range_start_row, node_range_start_col, _, _ = node:range()

    local params = vim.lsp.util.make_position_params()
    params.position.line = node_range_start_row
    params.position.character = node_range_start_col

    local tstools_client = vim.lsp.get_active_clients({ bufnr = bufnr, name = "typescript-tools" })[1]
    local client_response = tstools_client.request_sync("textDocument/references", params, 10000, bufnr)

    if client_response and client_response.result then
      for _, ref in ipairs(client_response.result) do
        if ref and ref.uri then
          local path = vim.uri_to_fname(ref.uri)
          if path ~= vim.fn.expand("%") then
            unique_paths[path] = true
          end
        end
      end
    end
  end

  return vim.tbl_keys(unique_paths)
end

M.move_selection_to_new_path = function(new_path)
  local start_row, start_col = unpack(vim.api.nvim_buf_get_mark(0, "<"))
  local end_row, end_col = unpack(vim.api.nvim_buf_get_mark(0, ">"))

  start_row = start_row - 1
  end_row = end_row - 1

  local lines = vim.api.nvim_buf_get_lines(0, start_row, end_row + 1, false)

  local file = io.open(new_path, "a+")
  if file then
    for _, line in ipairs(lines) do
      file:write(line .. "\n")
    end
    file:close()

    vim.api.nvim_buf_set_lines(0, start_row, end_row + 1, false, {})
    vim.cmd("write")
  else
    vim.notify("Failed to open file: " .. new_path, vim.log.levels.ERROR)
  end
end

M.update_imports = function(paths, new_path)
  if not paths or type(paths) ~= "table" or #paths == 0 then
    vim.notify("No reference paths stored", vim.log.levels.ERROR)
    return
  end

  for _, path in ipairs(paths) do
    local bufnr = vim.fn.bufadd(path)
    vim.api.nvim_buf_call(bufnr, function()
      ts_tools_api.add_missing_imports(true)
      vim.cmd("write")
    end)
  end
end

M.rename_export_to_unique = function(bufnr, node, unique_name)
  local start_row, start_col, _ = node:start()
  start_row = start_row + 1
  local params = {
    textDocument = vim.lsp.util.make_text_document_params(bufnr),
    position = { line = start_row, character = start_col },
    newName = unique_name,
    bufnr = bufnr,
  }
  local tstools_client = vim.lsp.get_active_clients({ bufnr = bufnr, name = "typescript-tools" })[1]
  local status, err = tstools_client.request_sync("textDocument/rename", params, 10000, bufnr)
  if status == nil or status.err or err or status.result == nil then
    return false
  end

  vim.lsp.util.apply_workspace_edit(status.result, tstools_client.offset_encoding)
end

M.rename_export_back_to_original = function(bufnr, node, original_name)
  local start_row, start_col, _ = node:start()
  start_row = start_row + 1
  local params = {
    textDocument = vim.lsp.util.make_text_document_params(bufnr),
    position = { line = start_row, character = start_col },
    newName = original_name,
    bufnr = bufnr,
  }
  local tstools_client = vim.lsp.get_active_clients({ bufnr = bufnr, name = "typescript-tools" })[1]
  local status, err = tstools_client.request_sync("textDocument/rename", params, 10000, bufnr)
  if status == nil or status.err or err or status.result == nil then
    return false
  end

  vim.lsp.util.apply_workspace_edit(status.result, tstools_client.offset_encoding)
end

M.generate_unique_name = function(node)
  local start_row, start_col, _ = node:start()
  start_row = start_row + 1
  return string.format("unique_%s_%d_%d", node:type(), start_row, start_col)
end

M.ts_move_exports = function()
  vim.ui.input({ prompt = "Enter new path: " }, function(input)
    if not input or input == "" then
      vim.notify("Please provide a new path", vim.log.levels.ERROR)
      return
    end
    local new_path = vim.fs.normalize(vim.fs.joinpath(vim.fn.expand("%:p:h"), input))

    local start_row, _ = unpack(vim.api.nvim_buf_get_mark(0, "<"))
    local end_row, _ = unpack(vim.api.nvim_buf_get_mark(0, ">"))

    start_row = start_row - 1
    end_row = end_row - 1

    local reference_paths = M.get_lsp_references_for_exports(start_row, end_row)
    local bufnr = vim.api.nvim_get_current_buf()
    local export_nodes = M.query_export_names(bufnr, start_row, end_row)

    for _, node in ipairs(export_nodes) do
      local unique_name = M.generate_unique_name(node)
      M.rename_export_to_unique(bufnr, node, unique_name)
    end

    M.move_selection_to_new_path(new_path)
    M.update_imports(reference_paths, new_path)

    for _, node in ipairs(export_nodes) do
      local original_name = vim.treesitter.get_node_text(node, bufnr)
      M.rename_export_back_to_original(bufnr, node, original_name)
    end
  end)
end

return M
