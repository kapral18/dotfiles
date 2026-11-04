local M = {}
local TIMEOUT_MS = 10000

local function fail(message)
  vim.notify(message, vim.log.levels.ERROR)
end

local function request(client, method, params, bufnr)
  local response, err = client:request_sync(method, params, TIMEOUT_MS, bufnr)
  if err or not response or response.err then
    fail("TypeScript refactor failed: " .. vim.inspect(err or (response and response.err)))
    return nil
  end
  return response.result
end

M.ts_move_exports = function()
  local source = vim.api.nvim_get_current_buf()
  local client = vim.lsp.get_clients({ bufnr = source, name = "typescript-tools" })[1]
  if not client then
    fail("typescript-tools LSP client not found")
    return
  end
  local source_path = vim.api.nvim_buf_get_name(source)
  local start_row = vim.api.nvim_buf_get_mark(source, "<")[1] - 1
  local end_row = vim.api.nvim_buf_get_mark(source, ">")[1] - 1
  if start_row < 0 or end_row < start_row then
    fail("Select the declarations to move")
    return
  end
  local tick = vim.api.nvim_buf_get_changedtick(source)
  local encoding = client.offset_encoding or "utf-16"
  local last_line = vim.api.nvim_buf_get_lines(source, end_row, end_row + 1, false)[1] or ""
  local params = {
    textDocument = vim.lsp.util.make_text_document_params(source),
    range = {
      start = { line = start_row, character = 0 },
      ["end"] = { line = end_row, character = vim.str_utfindex(last_line, encoding) },
    },
    context = { diagnostics = {}, only = { "refactor" } },
  }

  vim.ui.input({ prompt = "Enter new path: " }, function(input)
    if not input or input == "" then
      return
    end
    if not vim.api.nvim_buf_is_valid(source) or vim.api.nvim_buf_get_changedtick(source) ~= tick then
      fail("Source changed while choosing the target; select the declarations again")
      return
    end
    local target =
      vim.fs.normalize(input:sub(1, 1) == "/" and input or vim.fs.joinpath(vim.fs.dirname(source_path), input))
    if target == source_path then
      fail("Choose a different target file")
      return
    end
    local loaded_ticks = {}
    for _, buf in ipairs(vim.api.nvim_list_bufs()) do
      if vim.api.nvim_buf_is_loaded(buf) then
        loaded_ticks[buf] = vim.api.nvim_buf_get_changedtick(buf)
        if vim.api.nvim_buf_get_name(buf) == target and vim.bo[buf].modified then
          fail("Save the target buffer before moving declarations")
          return
        end
      end
    end

    local actions = request(client, "textDocument/codeAction", params, source)
    if not actions then
      return
    end
    local action
    for _, candidate in ipairs(actions) do
      if candidate.data and candidate.data.refactor == "Move to file" and candidate.data.action == "Move to file" then
        action = vim.deepcopy(candidate)
        break
      end
    end
    if not action then
      fail("TypeScript cannot move this selection to a file")
      return
    end
    action.command = nil
    action.data.interactiveRefactorArguments = { targetFile = target }
    local result = request(client, "codeAction/resolve", action, source)
    local edit = result and result.edit
    if not edit or edit.documentChanges or not edit.changes or vim.tbl_isempty(edit.changes) then
      fail("TypeScript returned no text edits for this target")
      return
    end

    local snapshots = {}
    for uri in pairs(edit.changes) do
      local buf = vim.uri_to_bufnr(uri)
      vim.fn.bufload(buf)
      if loaded_ticks[buf] and loaded_ticks[buf] ~= vim.api.nvim_buf_get_changedtick(buf) then
        fail("An affected buffer changed during the refactor; try again")
        return
      end
      if not vim.bo[buf].modifiable or vim.bo[buf].readonly then
        fail("An affected buffer is not writable: " .. vim.api.nvim_buf_get_name(buf))
        return
      end
      snapshots[buf] = {
        lines = vim.api.nvim_buf_get_lines(buf, 0, -1, false),
        modified = vim.bo[buf].modified,
        listed = vim.bo[buf].buflisted,
      }
    end
    local ok, err = pcall(vim.lsp.util.apply_workspace_edit, edit, encoding)
    if not ok then
      for buf, snapshot in pairs(snapshots) do
        vim.api.nvim_buf_set_lines(buf, 0, -1, false, snapshot.lines)
        vim.bo[buf].modified = snapshot.modified
        vim.bo[buf].buflisted = snapshot.listed
      end
      fail("TypeScript refactor was rolled back: " .. tostring(err))
      return
    end
    vim.notify("Moved declarations to " .. target .. "; review and save the affected buffers", vim.log.levels.INFO)
  end)
end

return M
