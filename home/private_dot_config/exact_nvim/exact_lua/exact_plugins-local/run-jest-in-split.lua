local M = {}

local test_types = { it = true, test = true, describe = true }

local function escape_jest_regex(str)
  local escapes = {
    ["\\"] = "\\\\",
    ["^"] = "\\^",
    ["$"] = "\\$",
    ["."] = "\\.",
    ["|"] = "\\|",
    ["?"] = "\\?",
    ["*"] = "\\*",
    ["+"] = "\\+",
    ["("] = "\\(",
    [")"] = "\\)",
    ["["] = "\\[",
    ["]"] = "\\]",
    ["{"] = "\\{",
    ["}"] = "\\}",
  }
  return str:gsub("[\\^$.|?*+()%[%]{}]", escapes)
end

M.escape_shell_arg = function(str)
  return "'" .. str:gsub("'", "'\\''") .. "'"
end

M.get_current_test_name = function()
  local bufnr = vim.api.nvim_get_current_buf()
  local parser = vim.treesitter.get_parser(bufnr)
  if not parser then
    return nil, nil
  end

  local root = parser:parse()[1]:root()
  local cursor = vim.api.nvim_win_get_cursor(0)
  local row = cursor[1] - 1
  local col = cursor[2]

  local function get_test_type(node)
    while node do
      local node_type = node:type()
      if node_type == "identifier" then
        return vim.treesitter.get_node_text(node, bufnr)
      elseif node_type == "member_expression" then
        node = node:field("object")[1]
      else
        break
      end
    end
    return nil
  end

  local function process_template(node)
    local parts = {}
    for child in node:iter_children() do
      local child_type = child:type()
      if child_type == "string_fragment" then
        local text = vim.treesitter.get_node_text(child, bufnr)
        table.insert(parts, escape_jest_regex(text))
      elseif child_type == "template_substitution" then
        table.insert(parts, ".*")
      end
    end
    return table.concat(parts)
  end

  local node = root:named_descendant_for_range(row, col, row, col)
  while node do
    if node:type() == "call_expression" then
      local fn_node = node:field("function")[1]
      local test_type = get_test_type(fn_node)

      if test_type and test_types[test_type] then
        local args = node:field("arguments")[1]
        if args and args:named_child_count() > 0 then
          local name_node = args:named_child(0)
          if not name_node then
            return nil, nil
          end

          local name_text
          local node_type = name_node:type()

          if node_type == "string" then
            local raw_text = vim.treesitter.get_node_text(name_node, bufnr):sub(2, -2)
            name_text = escape_jest_regex(raw_text)
          elseif node_type == "template_string" then
            name_text = process_template(name_node)
          else
            name_text = nil
          end

          return name_text, test_type
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
  local pattern = test_name .. suffix
  local arg = "-t " .. M.escape_shell_arg(pattern) .. update_arg
  M.run_jest_cmd(arg)
end

return M
