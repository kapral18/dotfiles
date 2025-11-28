local util = require("util")

local M = {}

local test_types = { it = true, test = true, describe = true }
local jest_script_priority = {
  "test",
  "test:unit",
  "test:jest",
  "jest",
  "jest:unit",
  "test:coverage",
  "jest:coverage",
}
local jest_config_candidates = {
  "jest.config.js",
  "jest.config.dev.js",
  "jest.integration.config.js",
}

local escape_shell_arg = util.fs.escape_shell_arg

local script_runner_builders = {
  yarn = function(script_name, file_path, root_dir)
    if root_dir then
      return string.format("yarn --cwd %s %s %s", escape_shell_arg(root_dir), script_name, file_path)
    end
    return string.format("yarn %s %s", script_name, file_path)
  end,
  npm = function(script_name, file_path, root_dir)
    if root_dir then
      return string.format("npm --prefix %s run %s -- %s", escape_shell_arg(root_dir), script_name, file_path)
    end
    return string.format("npm run %s -- %s", script_name, file_path)
  end,
  pnpm = function(script_name, file_path, root_dir)
    if root_dir then
      return string.format("pnpm --dir %s run %s -- %s", escape_shell_arg(root_dir), script_name, file_path)
    end
    return string.format("pnpm run %s -- %s", script_name, file_path)
  end,
  bun = function(script_name, file_path, root_dir)
    if root_dir then
      return string.format("bun --cwd %s run %s -- %s", escape_shell_arg(root_dir), script_name, file_path)
    end
    return string.format("bun run %s -- %s", script_name, file_path)
  end,
}

local function find_jest_script(scripts)
  if type(scripts) ~= "table" then
    return nil, nil
  end

  for _, name in ipairs(jest_script_priority) do
    if type(scripts[name]) == "string" then
      return name, scripts[name]
    end
  end

  return nil, nil
end

local PACKAGE_MANAGER_LOCKS = {
  yarn = "yarn.lock",
  npm = "package-lock.json",
  pnpm = "pnpm-lock.yaml",
  bun = "bun.lockb",
}

local PACKAGE_MANAGER_PRIORITY = { "yarn", "npm", "pnpm", "bun" }

local function detect_runner_in_dir(dir)
  if not dir or dir == "" then
    return nil
  end

  local normalized = vim.fn.fnamemodify(dir, ":p")
  for _, manager in ipairs(PACKAGE_MANAGER_PRIORITY) do
    local lock = PACKAGE_MANAGER_LOCKS[manager]
    if lock and util.file_exists(normalized .. "/" .. lock) then
      return manager
    end
  end

  return nil
end

local function detect_script_runner(search_dirs)
  if not search_dirs then
    return nil
  end

  if type(search_dirs) == "string" then
    search_dirs = { search_dirs }
  end

  for _, dir in ipairs(search_dirs) do
    local runner = detect_runner_in_dir(dir)
    if runner then
      return runner
    end
  end

  return nil
end

local function find_jest_binary(search_dirs)
  if not search_dirs then
    return nil
  end

  if type(search_dirs) == "string" then
    search_dirs = { search_dirs }
  end

  for _, dir in ipairs(search_dirs) do
    if dir and dir ~= "" then
      local normalized = vim.fn.fnamemodify(dir, ":p")
      -- Use joinpath to avoid accidental double slashes
      local possible_jest_paths = {
        vim.fs.joinpath(normalized, "node_modules", ".bin", "jest"),
        vim.fs.joinpath(normalized, "node_modules", "jest", "bin", "jest.js"),
      }

      for _, path in ipairs(possible_jest_paths) do
        if util.file_exists(path) then
          return path
        end
      end
    end
  end

  return nil
end

local function find_nearest_jest_config(test_path, root_dir)
  if not test_path or test_path == "" then
    return nil
  end

  local dir = vim.fn.fnamemodify(test_path, ":p:h")
  local normalized_root = root_dir and vim.fn.fnamemodify(root_dir, ":p") or nil

  while dir and dir ~= "" do
    for _, candidate in ipairs(jest_config_candidates) do
      local config_path = dir .. "/" .. candidate
      if util.file_exists(config_path) then
        return config_path
      end
    end

    if normalized_root and dir == normalized_root then
      break
    end

    local parent = vim.fn.fnamemodify(dir, ":h")
    if not parent or parent == dir then
      break
    end
    dir = parent
  end

  return nil
end

-- Extended Jest config discovery with prompt-and-cache when multiple are found
local JEST_CONFIG_EXTS_SET = { js = true, cjs = true, mjs = true, ts = true, cts = true, mts = true }

local function is_jest_config_filename(name)
  if type(name) ~= "string" then
    return false
  end
  -- Accept names like: jest.config.js, jest.config.dev.js, jest.dev.config.js, jest.integration.config.ts, etc.
  if
    not name:match("^jest%..*config%..+$")
    and not name:match("^jest%.config%..+$")
    and not name:match("^jest.*config%..+$")
  then
    return false
  end
  local ext = name:match("%.([%w]+)$")
  return ext and JEST_CONFIG_EXTS_SET[ext] or false
end

local function list_jest_configs_in_dir(dir)
  if not dir or dir == "" then
    return {}
  end
  local ok, entries = pcall(vim.fn.readdir, dir)
  if not ok or type(entries) ~= "table" then
    return {}
  end
  local results = {}
  for _, name in ipairs(entries) do
    if is_jest_config_filename(name) then
      local full = dir .. "/" .. name
      if util.file_exists(full) then
        table.insert(results, full)
      end
    end
  end
  return results
end

local function collect_jest_configs_upwards(start_dir, stop_dir)
  local dir = start_dir and vim.fn.fnamemodify(start_dir, ":p") or nil
  local stop = stop_dir and vim.fn.fnamemodify(stop_dir, ":p") or nil
  local results = {}
  while dir and dir ~= "" do
    local found = list_jest_configs_in_dir(dir)
    for _, p in ipairs(found) do
      table.insert(results, p)
    end
    if stop and dir == stop then
      break
    end
    local parent = vim.fn.fnamemodify(dir, ":h")
    if not parent or parent == dir then
      break
    end
    dir = parent
  end
  return results
end

local function get_git_branch(cwd)
  local args = { "git" }
  if cwd and cwd ~= "" then
    table.insert(args, "-C")
    table.insert(args, vim.fn.fnamemodify(cwd, ":p"))
  end
  table.insert(args, "rev-parse")
  table.insert(args, "--abbrev-ref")
  table.insert(args, "HEAD")
  local lines = vim.fn.systemlist(args)
  if vim.v.shell_error ~= 0 or not lines or #lines == 0 then
    return "unknown"
  end
  return lines[1]
end

local function get_cache_file_path()
  local cache_dir = vim.fn.stdpath("cache") .. "/run-jest-in-split"
  if vim.fn.isdirectory(cache_dir) == 0 then
    pcall(vim.fn.mkdir, cache_dir, "p")
  end
  return cache_dir .. "/jest-config-choices.json"
end

local function load_config_cache()
  local path = get_cache_file_path()
  if not util.file_exists(path) then
    return {}
  end
  local content = select(1, util.safe_file_read(path))
  if not content or content == "" then
    return {}
  end
  local ok, data = pcall(vim.fn.json_decode, content)
  if ok and type(data) == "table" then
    return data
  end
  return {}
end

local function save_config_cache(cache_tbl)
  local path = get_cache_file_path()
  local ok, json = pcall(vim.fn.json_encode, cache_tbl)
  if not ok then
    return false
  end
  local success = select(1, util.safe_file_write(path, json, "w"))
  return success == true
end

local function make_cache_key(project_root, branch, test_path)
  return (project_root or "") .. "|" .. (branch or "") .. "|" .. (vim.fn.fnamemodify(test_path or "", ":p"))
end

local function discover_package_context(test_path, project_root)
  local normalized_root = project_root and vim.fn.fnamemodify(project_root, ":p") or nil
  local dir = test_path and vim.fn.fnamemodify(test_path, ":p:h") or nil

  local function try_dir(current_dir)
    if not current_dir or current_dir == "" then
      return nil
    end

    local normalized = vim.fn.fnamemodify(current_dir, ":p")
    local package_json_path = normalized .. "/package.json"
    local has_package = util.file_exists(package_json_path)
    local runner = detect_runner_in_dir(normalized)

    if has_package then
      local scripts = {}
      local ok_read, contents = pcall(vim.fn.readfile, package_json_path)
      if ok_read then
        local ok_decode, decoded = pcall(vim.fn.json_decode, table.concat(contents, "\n"))
        if ok_decode and type(decoded) == "table" then
          scripts = decoded.scripts or {}
        end
      end

      local script_name, script_command = find_jest_script(scripts)

      if runner then
        return {
          package_json_path = package_json_path,
          package_root = normalized,
          script_name = script_name,
          script_command = script_command,
          runner = runner,
        }
      end

      if script_name then
        return {
          package_json_path = package_json_path,
          package_root = normalized,
          script_name = script_name,
          script_command = script_command,
          runner = detect_script_runner({ normalized, project_root }),
        }
      end
    elseif runner then
      return {
        package_json_path = nil,
        package_root = normalized,
        script_name = nil,
        script_command = nil,
        runner = runner,
      }
    end

    return nil
  end

  while dir and dir ~= "" do
    local context = try_dir(dir)
    if context then
      if not context.package_root then
        context.package_root = vim.fn.fnamemodify(dir, ":p")
      end
      if not context.package_json_path and util.file_exists(context.package_root .. "/package.json") then
        context.package_json_path = context.package_root .. "/package.json"
      end
      return context
    end

    if normalized_root and vim.fn.fnamemodify(dir, ":p") == normalized_root then
      break
    end

    local parent = vim.fn.fnamemodify(dir, ":h")
    if not parent or parent == dir then
      break
    end
    dir = parent
  end

  if normalized_root then
    local context = try_dir(normalized_root)
    if context then
      if not context.package_root then
        context.package_root = normalized_root
      end
      if not context.package_json_path and util.file_exists(context.package_root .. "/package.json") then
        context.package_json_path = context.package_root .. "/package.json"
      end
      return context
    end
  end

  if normalized_root then
    return {
      package_json_path = util.file_exists(normalized_root .. "/package.json")
          and normalized_root .. "/package.json"
        or nil,
      package_root = normalized_root,
      script_name = nil,
      script_command = nil,
      runner = detect_runner_in_dir(normalized_root),
    }
  end

  return nil
end

local function append_optional_arg(cmd, arg)
  if not arg or arg == "" then
    return cmd
  end

  if arg:sub(1, 1) == " " then
    return cmd .. arg
  end

  return cmd .. " " .. arg
end

local rel_to_base

local function build_script_runner_command(
  script_runner,
  script_name,
  file_path,
  arg,
  root_dir,
  project_root,
  explicit_config
)
  local builder = script_runner_builders[script_runner]
  local rel_file = rel_to_base(file_path:gsub("^'(.*)'$", "%1"), root_dir or project_root)
  local rel_escaped = escape_shell_arg(rel_file)

  -- Normalize arg and inject relative --config if provided
  local extra = arg or ""
  if explicit_config and not extra:match("%-%-config") then
    local rel_cfg = rel_to_base(explicit_config, root_dir or project_root)
    extra = append_optional_arg("--config " .. escape_shell_arg(rel_cfg), extra)
  end

  local base
  if builder then
    base = builder(script_name, rel_escaped, root_dir)
  else
    base = string.format("%s run %s -- %s", script_runner, script_name, rel_escaped)
  end

  return append_optional_arg(base, extra)
end

local function inject_inspect_into_node_script(script_command)
  if type(script_command) ~= "string" then
    return nil
  end

  if not script_command:match("^node%s") then
    return nil
  end

  if script_command:match("%-%-inspect%-brk") then
    return script_command
  end

  if script_command:match("%-%-inspect") then
    return script_command:gsub("%-%-inspect", "--inspect-brk", 1)
  end

  return script_command:gsub("^node%s+", "node --inspect-brk ", 1)
end

rel_to_base = function(path, base_dir)
  if not path or path == "" then
    return path
  end
  local abs = vim.fs.normalize(vim.fn.fnamemodify(path, ":p"))
  local base = vim.fs.normalize(vim.fn.fnamemodify(base_dir or vim.env.PWD or "", ":p"))
  base = base:gsub("/+$", "")
  if base ~= "" and abs:sub(1, #base + 1) == (base .. "/") then
    return abs:sub(#base + 2)
  end
  return abs
end

local function build_manual_jest_command(
  package_root,
  project_root,
  test_path,
  file_path_arg,
  arg,
  debug_mode,
  explicit_config
)
  local jest_path = find_jest_binary({ package_root, project_root })
  if not jest_path then
    vim.notify("Jest binary not found in node_modules", vim.log.levels.ERROR)
    return nil
  end

  local tokens = { "node" }
  if debug_mode then
    table.insert(tokens, "--inspect-brk")
  end

  table.insert(tokens, escape_shell_arg(rel_to_base(jest_path, project_root)))

  if debug_mode then
    table.insert(tokens, "--runInBand")
  end

  local config_path = explicit_config or find_nearest_jest_config(test_path, package_root or project_root)
  if config_path then
    table.insert(tokens, "--config")
    table.insert(tokens, escape_shell_arg(rel_to_base(config_path, project_root)))
  end

  -- file_path_arg contains already-escaped path; rebuild with project-relative path
  local raw_path = file_path_arg:match("^'(.*)'$") or file_path_arg
  local rel_file = rel_to_base(raw_path, project_root)
  local rel_escaped = escape_shell_arg(rel_file)
  table.insert(tokens, rel_escaped)

  local cmd = table.concat(tokens, " ")
  return append_optional_arg(cmd, arg)
end

local function build_debug_command(context, project_root, test_path, escaped_path, arg, explicit_config)
  if context and context.script_command then
    local injected = inject_inspect_into_node_script(context.script_command)
    if injected then
      local raw_path = escaped_path:match("^'(.*)'$") or escaped_path
      local base = string.format("%s %s", injected, escape_shell_arg(rel_to_base(raw_path, project_root)))
      local extra = arg or ""
      if explicit_config and not extra:match("%-%-config") then
        extra = extra .. " --config " .. escape_shell_arg(rel_to_base(explicit_config, project_root))
      end
      return append_optional_arg(base, extra)
    end
  end

  local package_root = context and context.package_root or nil
  return build_manual_jest_command(package_root, project_root, test_path, escaped_path, arg, true, explicit_config)
end

local function build_regular_command(context, project_root, test_path, escaped_path, arg, explicit_config)
  if context then
    local script_name = context.script_name
    local script_runner = context.runner

    if script_name and script_runner then
      return build_script_runner_command(
        script_runner,
        script_name,
        escaped_path,
        arg,
        context.package_root,
        project_root,
        explicit_config
      )
    end
  end

  local package_root = context and context.package_root or nil
  return build_manual_jest_command(package_root, project_root, test_path, escaped_path, arg, false, explicit_config)
end

local function open_jest_terminal(cmd, cwd)
  return require("util.terminal").run_in_split(cmd, { cwd = cwd, focus_original = true })
end

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
  local ok, parser = pcall(vim.treesitter.get_parser, bufnr)
  if not ok or not parser then
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

M.escape_shell_arg = escape_shell_arg
---@param debug_mode boolean|nil Whether to run Jest in debug mode
M.run_jest_cmd = function(arg, debug_mode)
  local root_dir = util.get_project_root()

  if not root_dir then
    vim.notify("No .git directory or yarn.lock or package-lock.json found", vim.log.levels.WARN)
    return
  end

  local test_file_path = vim.fn.expand("%:p")
  if not test_file_path or test_file_path == "" then
    vim.notify("Could not resolve test file path for current buffer", vim.log.levels.ERROR)
    return
  end

  -- locate nearest package.json starting from the test file directory and walking up to the project root
  local context = discover_package_context(test_file_path, root_dir)
  if not context then
    vim.notify("No package.json found in current or parent directories", vim.log.levels.ERROR)
    return
  end

  -- Resolve explicit jest config with prompt-and-cache when multiple are present
  local branch = get_git_branch(root_dir)
  local cache = load_config_cache()
  local key = make_cache_key(root_dir, branch, test_file_path)
  local explicit_config = cache[key]

  -- Invalidate stale cache entries
  if explicit_config and not util.file_exists(explicit_config) then
    cache[key] = nil
    save_config_cache(cache)
    explicit_config = nil
  end

  if not explicit_config then
    local start_dir = vim.fn.fnamemodify(test_file_path, ":p:h")
    local configs = collect_jest_configs_upwards(start_dir, context.package_root or root_dir)
    if #configs == 1 then
      explicit_config = configs[1]
    elseif #configs > 1 then
      local choices = {}
      for _, p in ipairs(configs) do
        local rel = vim.fn.fnamemodify(p, ":.")
        table.insert(choices, { label = rel ~= p and rel or p, value = p })
      end
      vim.ui.select(choices, {
        prompt = "Multiple Jest configs found. Choose one to remember:",
        format_item = function(item)
          return item.label
        end,
      }, function(choice)
        if not choice then
          return
        end
        cache[key] = choice.value
        save_config_cache(cache)
        M.run_jest_cmd(arg, debug_mode) -- re-run to pick up cache
      end)
      return
    end
  end

  local escaped_test_path = escape_shell_arg(test_file_path)
  local cmd
  if debug_mode then
    cmd = build_debug_command(context, root_dir, test_file_path, escaped_test_path, arg, explicit_config)
  else
    cmd = build_regular_command(context, root_dir, test_file_path, escaped_test_path, arg, explicit_config)
  end

  if not cmd then
    return
  end

  open_jest_terminal(cmd, context.package_root or root_dir)
end

M.close_terminal_buffer = function()
  require("util.terminal").close_all_terminals()
end

local function show_parametrized_prompt(pattern, update_arg, debug_mode)
  local choices = {
    { label = "Run all parameterized tests", kind = "pattern", value = pattern, extra = update_arg },
    { label = "Enter custom regex pattern", kind = "custom" },
  }

  local toggle_label
  local toggle_update_arg
  if update_arg ~= "" then
    toggle_label = "Run without update snapshots"
    toggle_update_arg = ""
  else
    toggle_label = "Run with update snapshots"
    toggle_update_arg = " --updateSnapshot"
  end

  table.insert(choices, { label = toggle_label, kind = "pattern", value = pattern, extra = toggle_update_arg })

  vim.ui.select(choices, {
    prompt = "Parameterized test detected:",
    format_item = function(item)
      return item.label
    end,
  }, function(choice)
    if not choice then
      return
    end

    if choice.kind == "custom" then
      vim.ui.input({ prompt = "Enter test regex: ", default = pattern }, function(input)
        if input then
          local arg = "-t " .. escape_shell_arg(input)
          if update_arg ~= "" then
            arg = arg .. update_arg
          end
          M.run_jest_cmd(arg, debug_mode)
        end
      end)
      return
    end

    local arg = "-t " .. escape_shell_arg(choice.value)
    if choice.extra ~= "" then
      arg = arg .. choice.extra
    end
    M.run_jest_cmd(arg, debug_mode)
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
    show_parametrized_prompt(pattern, update_arg, options.debug)
  else
    local arg = "-t " .. escape_shell_arg(pattern) .. update_arg --[[@as string]]
    M.run_jest_cmd(arg, options.debug)
  end
end

return M
