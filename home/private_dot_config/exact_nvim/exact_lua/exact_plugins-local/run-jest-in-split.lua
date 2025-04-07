local M = {}

local test_types = { it = true, test = true, describe = true }

---@param str string
M.escape_shell_arg = function(str)
  return str:gsub("['`$\"%%%^%*%+%?%[%]{%}%(%)|]", "\\%0")
end

M.get_current_test_name = function()
  local bufnr = vim.api.nvim_get_current_buf()
  local parser = vim.treesitter.get_parser(bufnr)
  if not parser then
    return nil, nil
  end

  local root = parser:parse()[1]:root()
  local cursor = vim.api.nvim_win_get_cursor(0)
  local row = cursor[1] - 1 -- TS uses 0-based row
  local col = cursor[2]

  local node = root:named_descendant_for_range(row, col, row, col)
  while node do
    if node:type() == "call_expression" then
      local fn_node = node:field("function")[1]
      if fn_node and fn_node:type() == "identifier" then
        local test_type = vim.treesitter.get_node_text(fn_node, bufnr)
        if test_types[test_type] then
          local args = node:field("arguments")[1]
          if args and args:named_child_count() > 0 then
            local name_node = args:named_child(0)

            if not name_node then
              return nil, nil
            end

            local name_text = vim.treesitter.get_node_text(name_node, bufnr)

            if name_node:type() == "string" or name_node:type() == "template_string" then
              name_text = name_text:sub(2, -2)
            end

            return name_text, test_type
          end
        end
      end
    end
    node = node:parent()
  end
  return nil, nil
end

---@param arg? string
M.run_jest_cmd = function(arg)
  local cmd = "node scripts/jest " .. vim.fn.expand("%:p")
  if arg then
    cmd = cmd .. " " .. arg
  end

  local original_win = vim.api.nvim_get_current_win()

  vim.cmd.vsplit()
  vim.cmd.terminal()
  vim.api.nvim_chan_send(vim.bo.channel, cmd .. "\n")

  -- Return focus to the original window
  vim.api.nvim_set_current_win(original_win)
end

M.close_terminal_buffer = function()
  for _, buf in ipairs(vim.api.nvim_list_bufs()) do
    if vim.bo[buf].buftype == "terminal" then
      vim.fn.jobstop(vim.bo[buf].channel)
      vim.cmd("silent! bdelete! " .. buf)
    end
  end
end

---@param options? { entire_file?: boolean, update_snapshots?: boolean }
M.run_jest_in_split = function(options)
  options = options or {}
  M.close_terminal_buffer()

  local update_arg = options.update_snapshots and " --updateSnapshot" or ""
  if options.entire_file then
    M.run_jest_cmd(update_arg)
    return
  end

  local test_name, test_type = M.get_current_test_name()
  if not test_name then
    M.run_jest_cmd(update_arg)
    return
  end

  local suffix = test_type == "describe" and "" or "$"
  local escaped_name = M.escape_shell_arg(test_name)
  local arg = "-t '" .. escaped_name .. suffix .. "'" .. update_arg
  M.run_jest_cmd(arg)
end

return M
