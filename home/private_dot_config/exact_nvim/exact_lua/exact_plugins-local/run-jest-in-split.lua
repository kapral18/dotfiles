local M = {}

local test_types = { it = true, test = true, describe = true }

local function escape_jest_regex(str, is_parametrized)
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

  -- First escape special characters
  str = str:gsub("[\\^$.|?*+()%[%]{}]", function(c)
    return escapes[c]
  end)

  if is_parametrized then
    -- Handle printf format specifiers
    str = str:gsub("%%%%", "__DOUBLE_PERCENT__")
    str = str:gsub("%%[#pidjfso]", ".*")
    str = str:gsub("__DOUBLE_PERCENT__", "%%")

    -- Handle $variable substitution
    str = str:gsub("%$%$", "__DOUBLE_DOLLAR__")
    str = str:gsub("%$[%a#][%.%w]*", ".*")
    str = str:gsub("__DOUBLE_DOLLAR__", "%$")
  end

  -- Handle template substitutions in all tests
  str = str:gsub("%${.-}", ".*")

  return str
end

local function is_each_call(node, bufnr)
  if node:type() == "call_expression" then
    local fn_node = node:field("function")[1]
    if fn_node:type() == "member_expression" then
      local property = vim.treesitter.get_node_text(fn_node:field("property")[1], bufnr)
      return property == "each"
    end
  end
  return false
end

local function get_test_type(node, bufnr)
  local current_node = node
  local is_parametrized = false

  while current_node do
    if is_each_call(current_node, bufnr) then
      local object_node = current_node:field("function")[1]:field("object")[1]
      local test_type = vim.treesitter.get_node_text(object_node, bufnr)
      return test_type, true
    end

    if current_node:type() == "call_expression" then
      local fn_node = current_node:field("function")[1]
      local test_type = vim.treesitter.get_node_text(fn_node, bufnr)
      if test_types[test_type] then
        return test_type, false
      end
    end

    current_node = current_node:parent()
  end

  return nil, false
end

local function get_test_name_node(node, bufnr)
  local args = node:field("arguments")[1]
  if not args then
    return nil
  end

  -- Handle parameterized tests: describe.each()('name', ...)
  if is_each_call(node, bufnr) then
    local parent_call = node:parent()
    if parent_call and parent_call:type() == "call_expression" then
      local parent_args = parent_call:field("arguments")[1]
      return parent_args:named_child(0)
    end
  end

  -- Handle regular tests: describe('name', ...)
  return args:named_child(0)
end

local function process_template(node, bufnr, is_parametrized)
  local parts = {}
  for child in node:iter_children() do
    local child_type = child:type()
    if child_type == "string_fragment" then
      local text = vim.treesitter.get_node_text(child, bufnr)
      table.insert(parts, escape_jest_regex(text, is_parametrized))
    elseif child_type == "template_substitution" then
      table.insert(parts, ".*")
    end
  end
  return table.concat(parts)
end

M.get_current_test_name = function()
  local bufnr = vim.api.nvim_get_current_buf()
  local parser = vim.treesitter.get_parser(bufnr)
  if not parser then
    return nil, nil, false
  end

  local root = parser:parse()[1]:root()
  local cursor = vim.api.nvim_win_get_cursor(0)
  local row = cursor[1] - 1
  local col = cursor[2]

  local node = root:named_descendant_for_range(row, col, row, col)
  while node do
    if node:type() == "call_expression" then
      local test_type, is_parametrized = get_test_type(node, bufnr)
      if test_type and test_types[test_type] then
        local name_node = get_test_name_node(node, bufnr)
        if not name_node then
          return nil, nil, is_parametrized
        end

        local node_type = name_node:type()
        local name_text

        if node_type == "string" then
          local raw_text = vim.treesitter.get_node_text(name_node, bufnr):sub(2, -2)
          name_text = escape_jest_regex(raw_text, is_parametrized)
        elseif node_type == "template_string" then
          name_text = process_template(name_node, bufnr, is_parametrized)
        else
          name_text = nil
        end

        return name_text, test_type, is_parametrized
      end
    end
    node = node:parent()
  end
  return nil, nil, false
end

M.escape_shell_arg = function(str)
  return "'" .. str:gsub("'", "'\\''") .. "'"
end

M.run_jest_cmd = function(arg)
  local cmd = "node scripts/jest " .. vim.fn.expand("%:p")
  if arg then
    cmd = cmd .. " " .. arg
  end

  local original_win = vim.api.nvim_get_current_win()
  vim.cmd.vsplit()
  vim.cmd.terminal()
  vim.api.nvim_chan_send(vim.bo.channel, cmd .. "\n")
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

local function show_parametrized_prompt(pattern)
  local choices = {
    { label = "Run all parameterized tests", value = pattern },
    { label = "Enter custom regex pattern", value = "custom" },
    { label = "Run with update snapshots", value = pattern .. " --updateSnapshot" },
  }

  vim.ui.select(choices, {
    prompt = "Parameterized test detected:",
    format_item = function(item)
      return item.label
    end,
  }, function(choice)
    if choice then
      if choice.value == "custom" then
        vim.ui.input({ prompt = "Enter test regex: ", default = pattern }, function(input)
          if input then
            M.run_jest_cmd("-t " .. M.escape_shell_arg(input))
          end
        end)
      else
        M.run_jest_cmd("-t " .. M.escape_shell_arg(choice.value))
      end
    end
  end)
end

M.run_jest_in_split = function(options)
  options = options or {}
  M.close_terminal_buffer()

  local update_arg = options.update_snapshots and " --updateSnapshot" or ""
  if options.entire_file then
    M.run_jest_cmd(update_arg)
    return
  end

  local test_name, test_type, is_parametrized = M.get_current_test_name()
  if not test_name then
    M.run_jest_cmd(update_arg)
    return
  end

  local pattern
  if test_type == "describe" then
    pattern = "^" .. test_name
  else
    pattern = test_name .. "$"
  end

  if is_parametrized then
    show_parametrized_prompt(pattern .. update_arg)
  else
    local arg = "-t " .. M.escape_shell_arg(pattern) .. update_arg
    M.run_jest_cmd(arg)
  end
end

return M
