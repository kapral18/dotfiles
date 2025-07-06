local M = {}

local function find_package_json(path)
  local found = vim.fs.find("package.json", { path = path, upward = true, stop = vim.uv.os_homedir() })
  return #found > 0 and found[1] or nil
end

local function find_rule_file(node_modules_path, rule_name)
  return vim.fs.find(rule_name .. ".js", { path = node_modules_path, type = "file" })[1]
end

function M.get_extends_path(node_modules_path, str)
  if vim.startswith(str, "plugin:") then
    local config = str:gsub("plugin:", "")
    local config_parts = vim.split(config, "/")
    local config_name, config_version = config_parts[1], config_parts[2]

    local base_path = vim.startswith(config_name, "@")
        and vim.fs.joinpath(node_modules_path, config_name, "eslint-plugin")
      or vim.fs.joinpath(node_modules_path, "eslint-plugin-" .. config_name)

    if config_version then
      return find_rule_file(base_path, config_version) or nil, base_path
    else
      return nil, base_path
    end
  elseif vim.startswith(str, "eslint:") then
    local eslint_path = vim.fs.joinpath(node_modules_path, "eslint")
    return find_package_json(eslint_path) or nil, eslint_path
  else
    local config_name = vim.split(str, ":")[1]
    local config_path = vim.fs.joinpath(node_modules_path, "eslint-config-" .. config_name)
    return find_package_json(config_path) or nil, config_path
  end
end

function M.get_plugins_path(node_modules_path, str)
  local plugin_path = vim.startswith(str, "@") and vim.fs.joinpath(node_modules_path, str, "eslint-plugin")
    or vim.fs.joinpath(node_modules_path, "eslint-plugin-" .. str)
  return find_package_json(plugin_path)
end

function M.get_rules_path(node_modules_path, str)
  local config_parts = vim.split(str, "/")
  local rule_scope, rule_name = config_parts[1], config_parts[2]

  local found_rules = vim.fs.find((rule_name or rule_scope) .. ".js", { path = node_modules_path, type = "file" })

  if #found_rules == 0 then
    if vim.startswith(rule_scope, "@") then
      return find_package_json(vim.fs.joinpath(node_modules_path, rule_scope))
    elseif rule_name then
      return find_package_json(vim.fs.joinpath(node_modules_path, "eslint-plugin-" .. rule_scope))
    end
    return nil
  elseif #found_rules > 1 then
    vim.ui.select(found_rules, {
      prompt = "Select rule",
      format_item = function(item)
        return vim.fn.fnamemodify(item, ":.")
      end,
    }, function(selected)
      if selected then
        vim.cmd("edit " .. selected)
      else
        vim.notify("No rule selected", vim.log.levels.WARN)
      end
    end)
    return false
  else
    return found_rules[1]
  end
end

function M.get_eslint_path()
  local buf_dir = vim.fs.dirname(vim.api.nvim_buf_get_name(0))
  local root_dir = vim.fs.find({ ".git", "yarn.lock", "package-lock.json" }, { upward = true, path = buf_dir })[1]
  if not root_dir then
    vim.notify("No .git directory or yarn.lock or package-lock.json found", vim.log.levels.WARN)
    return
  end

  local node_modules =
    vim.fs.find("node_modules", { upward = true, type = "directory", stop = root_dir, path = buf_dir })

  if #node_modules == 0 then
    vim.notify("No node_modules directory found", vim.log.levels.WARN)
    return
  end

  local cursor_row, cursor_col = unpack(vim.api.nvim_win_get_cursor(0))
  cursor_row = cursor_row - 1

  local bufnr = vim.api.nvim_get_current_buf()
  local parser = vim.treesitter.get_parser(bufnr, vim.bo.filetype)
  local tree = parser:parse()[1]
  local root = tree:root()

  local cursor_node = root:descendant_for_range(cursor_row, cursor_col, cursor_row, cursor_col)

  if not cursor_node then
    vim.notify("Cursor was not within a node", vim.log.levels.WARN)
    return
  end

  local cursor_node_text = vim.treesitter.get_node_text(cursor_node, bufnr)

  local function find_eslint_key(node)
    if node:type() == "pair" and node:child_count() > 0 then
      local key_node = node:child(0)
      if key_node and (key_node:type() == "property_identifier" or key_node:type() == "string") then
        local eslint_key = vim.treesitter.get_node_text(key_node, bufnr)
        if key_node:type() == "string" then
          eslint_key = eslint_key:gsub('"', "")
        end
        return eslint_key
      end
    end
    return nil
  end

  local function process_eslint_key(eslint_key)
    for _, node_module in ipairs(node_modules) do
      local result
      if eslint_key == "extends" then
        result = M.get_extends_path(node_module, cursor_node_text)
      elseif eslint_key == "plugins" then
        result = M.get_plugins_path(node_module, cursor_node_text)
      elseif eslint_key == "rules" then
        result = M.get_rules_path(node_module, cursor_node_text)
      end

      if result then
        return result
      end
    end

    vim.notify("No " .. eslint_key .. " found for: " .. cursor_node_text, vim.log.levels.WARN)
    return nil
  end

  local node = cursor_node
  while node do
    local eslint_key = find_eslint_key(node)
    if eslint_key then
      return process_eslint_key(eslint_key)
    end
    node = node:parent()
  end
end

function M.open_eslint_path()
  local eslint_path = M.get_eslint_path()
  if eslint_path then
    vim.cmd("edit " .. eslint_path)
  end
end

return M
