local common_utils = require("utils.common")

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

  local placeholder = "__PARAM_PATTERN__"

  -- Handle template substitutions from non-parameterized tests
  str = str:gsub("__SUB__", placeholder)

  if is_parametrized then
    -- Handle Jest's parameterized test patterns
    -- Replace ${...}, %s, $variable with placeholder
    str = str:gsub("%${.-}", placeholder)

    str = str:gsub("%%%%", "__DOUBLE_PERCENT__")
    str = str:gsub("%%[#pidjfso]", placeholder)
    str = str:gsub("__DOUBLE_PERCENT__", "%%")

    str = str:gsub("%$%$", "__DOUBLE_DOLLAR__")
    str = str:gsub("%$[%a#][%.%w]*", placeholder)
    str = str:gsub("__DOUBLE_DOLLAR__", "%$")
  end

  -- Escape regex special characters
  str = str:gsub("[\\^$.|?*+()%[%]{}]", function(c)
    return escapes[c] or c
  end)

  -- Replace all placeholders with .*
  str = str:gsub(placeholder, ".*")

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

local function get_test_name(node, bufnr)
  local name_node = node:field("arguments")[1]:named_child(0)
  if not name_node then
    return nil
  end

  local node_type = name_node:type()
  if node_type == "string" then
    return vim.treesitter.get_node_text(name_node, bufnr):sub(2, -2)
  elseif node_type == "template_string" then
    local parts = {}
    for child in name_node:iter_children() do
      local child_type = child:type()
      if child_type == "string_fragment" then
        table.insert(parts, vim.treesitter.get_node_text(child, bufnr))
      elseif child_type == "template_substitution" then
        table.insert(parts, "__SUB__")
      end
    end
    return table.concat(parts)
  end
  return nil
end

local function get_test_type_from_each_call(each_call_node, bufnr)
  if each_call_node:type() == "call_expression" then
    local fn_node = each_call_node:field("function")[1]
    if fn_node:type() == "member_expression" then
      local object_node = fn_node:field("object")[1]
      return vim.treesitter.get_node_text(object_node, bufnr)
    end
  end
  return nil
end

local function get_full_test_context(node, bufnr)
  local path = {}
  local current_node = node
  local is_leaf = false
  local has_parametrized = false

  while current_node do
    if current_node:type() == "call_expression" then
      local is_each = is_each_call(current_node, bufnr)
      local test_type, name, parametrized = nil, nil, false

      if is_each then
        -- Handle direct .each calls
        local parent_call = current_node:parent()
        if parent_call and parent_call:type() == "call_expression" then
          name = get_test_name(parent_call, bufnr)
          test_type = get_test_type_from_each_call(current_node, bufnr)
          parametrized = true
          current_node = parent_call
        end
      else
        -- Handle nested .each calls (e.g., describe.each()())
        local fn_node = current_node:field("function")[1]
        if fn_node:type() == "call_expression" and is_each_call(fn_node, bufnr) then
          test_type = get_test_type_from_each_call(fn_node, bufnr)
          name = get_test_name(current_node, bufnr)
          parametrized = true
        else
          test_type = vim.treesitter.get_node_text(fn_node, bufnr)
          name = get_test_name(current_node, bufnr)
        end
      end

      if test_types[test_type] and name then
        has_parametrized = has_parametrized or parametrized
        is_leaf = is_leaf or (test_type == "it" or test_type == "test")
        table.insert(path, 1, {
          name = escape_jest_regex(name, parametrized),
          is_leaf = test_type == "it" or test_type == "test",
        })
      end
    end

    current_node = current_node:parent()
  end

  return path, has_parametrized, is_leaf
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
  local path, has_parametrized, is_leaf = get_full_test_context(node, bufnr)

  if #path == 0 then
    return nil, nil, false
  end

  local full_path = {}
  for _, entry in ipairs(path) do
    table.insert(full_path, entry.name)
  end

  return table.concat(full_path, " "), is_leaf, has_parametrized
end

M.escape_shell_arg = function(str)
  return "'" .. str:gsub("'", [['\'']]) .. "'"
end

---@param arg string Additional arguments to pass to Jest
---@param debug_mode boolean|nil Whether to run Jest in debug mode
M.run_jest_cmd = function(arg, debug_mode)
  local root_dir = common_utils.get_project_root()

  if not root_dir then
    vim.notify("No .git directory or yarn.lock or package-lock.json found", vim.log.levels.WARN)
    return
  end

  -- check if package.json exists in root_dir using fs_stat
  local found_pkg_json_path = common_utils.file_exists(root_dir .. "/package.json") and root_dir .. "/package.json"
    or nil

  if not found_pkg_json_path then
    vim.notify("No package.json found in current or parent directories", vim.log.levels.ERROR)
    return
  end

  local cmd

  if debug_mode then
    -- For debug mode, we need to run Jest directly with node inspector
    local jest_path = nil

    -- Try to find jest binary
    local possible_jest_paths = {
      root_dir .. "/node_modules/.bin/jest",
      root_dir .. "/node_modules/jest/bin/jest.js",
    }

    for _, path in ipairs(possible_jest_paths) do
      if common_utils.file_exists(path) then
        jest_path = path
        break
      end
    end

    if not jest_path then
      vim.notify("Jest binary not found in node_modules", vim.log.levels.ERROR)
      return
    end

    -- Construct debug command
    cmd = "node --inspect-brk " .. jest_path .. " --runInBand " .. vim.fn.expand("%:p")
    if arg then
      cmd = cmd .. " " .. arg
    end

    -- Notify user about debug port
    vim.notify("Starting Jest in debug mode on port 9229. Attach your debugger.", vim.log.levels.INFO)
  else
    -- Normal mode - use package scripts
    local package_json = vim.fn.json_decode(vim.fn.readfile(found_pkg_json_path)) --[[@as {scripts?: table<string, string>}]]

    if not package_json.scripts then
      vim.notify("No scripts found in package.json", vim.log.levels.ERROR)
      return
    end

    local pkg_json_scripts = package_json.scripts --[[@as table<string, string>]]

    local jest_script_names = {
      "test",
      "test:unit",
      "test:jest",
      "jest",
      "jest:unit",
      "test:all",
      "jest:all",
      "test:watch",
      "jest:watch",
      "test:coverage",
      "jest:coverage",
    }

    local script_name = nil
    for _, name in ipairs(jest_script_names) do
      if pkg_json_scripts[name] then
        script_name = name
        break
      end
    end

    if not script_name then
      vim.notify("No jest script found in package.json", vim.log.levels.ERROR)
      return
    end

    local script_runner = nil

    if common_utils.file_exists(root_dir .. "/yarn.lock") then
      script_runner = "yarn"
    elseif common_utils.file_exists(root_dir .. "/package-lock.json") then
      script_runner = "npm"
    elseif common_utils.file_exists(root_dir .. "/pnpm-lock.yaml") then
      script_runner = "pnpm"
    elseif common_utils.file_exists(root_dir .. "/bun.lockb") then
      script_runner = "bun"
    end

    if not script_runner then
      vim.notify("No supported package manager lock file found", vim.log.levels.ERROR)
      return
    end

    cmd = script_runner .. " " .. script_name .. " " .. vim.fn.expand("%:p")
    if arg then
      cmd = cmd .. " " .. arg
    end
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

local function show_parametrized_prompt(pattern, debug_mode)
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
            M.run_jest_cmd("-t " .. M.escape_shell_arg(input), debug_mode)
          end
        end)
      else
        M.run_jest_cmd("-t " .. M.escape_shell_arg(choice.value), debug_mode)
      end
    end
  end)
end

---@class JestRunOptions
---@field update_snapshots? boolean Whether to update Jest snapshots
---@field entire_file? boolean Whether to run tests for the entire file
---@field debug? boolean Whether to run tests in debug mode

---Run Jest tests in a split terminal window
---@param options? JestRunOptions Options for running Jest tests
M.run_jest_in_split = function(options)
  options = options or {}
  M.close_terminal_buffer()

  local update_arg = options.update_snapshots and " --updateSnapshot" or ""
  if options.entire_file then
    M.run_jest_cmd(update_arg, options.debug)
    return
  end

  local test_name, is_leaf, is_parametrized = M.get_current_test_name()
  if not test_name then
    M.run_jest_cmd(update_arg, options.debug)
    return
  end

  local pattern
  if is_leaf then
    pattern = "^" .. test_name .. "$"
  else
    pattern = "^" .. test_name
  end

  pattern = pattern:gsub("%s+", " ") -- Normalize spaces

  if is_parametrized then
    show_parametrized_prompt(pattern .. update_arg, options.debug)
  else
    local arg = "-t " .. M.escape_shell_arg(pattern) .. update_arg --[[@as string]]
    M.run_jest_cmd(arg, options.debug)
  end
end

return M
