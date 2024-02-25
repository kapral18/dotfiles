local function get_extends_path(node_modules_path, str)
  local resulting_path = node_modules_path
  if vim.startswith(str, "plugin:") then
    local config = string.gsub(str, "plugin:", "")

    local separator = string.find(config, "/")

    local config_name = config
    local config_version = nil
    if separator ~= nil then
      local config_parts = vim.split(config, "/")
      config_name = config_parts[1]
      config_version = config_parts[2]
    end

    if vim.startswith(config_name, "@") then
      local starting_path = vim.fs.joinpath(resulting_path, config_name, "eslint-plugin")
      if config_version ~= nil then
        local found = vim.fs.find(config_version .. ".js", { path = starting_path })
        if vim.tbl_isempty(found) then
          return nil, starting_path
        end

        return found[1], nil
      else
        return nil, starting_path
      end
    end

    if config_version ~= nil then
      local starting_path = vim.fs.joinpath(resulting_path, "eslint-plugin-" .. config_name)
      local found = vim.fs.find(config_version .. ".js", { path = starting_path })
      if vim.tbl_isempty(found) then
        return nil, starting_path
      end
      return found[1], nil
    else
      return nil, vim.fs.joinpath(resulting_path, "eslint-plugin-" .. config_name)
    end
  end

  if vim.startswith(str, "eslint:") then
    local starting_path = vim.fs.joinpath(resulting_path, "eslint")
    local found = vim.fs.find("package.json", { path = starting_path })
    if vim.tbl_isempty(found) then
      return nil, starting_path
    end
    return found[1], nil
  end

  local separator = string.find(str, ":")
  local config_name = str

  if separator ~= nil then
    config_name, _ = vim.split(str, ":")
  end

  local starting_path = vim.fs.joinpath(resulting_path, "eslint-config-" .. config_name)
  local found = vim.fs.find("package.json", { path = starting_path })
  if vim.tbl_isempty(found) then
    return nil, starting_path
  end
  return found[1], nil
end

local function get_plugins_path(node_modules_path, str)
  local resulting_path = node_modules_path
  if vim.startswith(str, "@") then
    local starting_path = vim.fs.joinpath(resulting_path, str, "eslint-plugin")
    local found = vim.fs.find("package.json", { path = starting_path })
    if vim.tbl_isempty(found) then
      return nil
    end
    return found[1]
  end

  local starting_path = vim.fs.joinpath(resulting_path, "eslint-plugin-" .. str)
  local found = vim.fs.find("package.json", { path = starting_path })
  if vim.tbl_isempty(found) then
    return nil
  end
  return found[1]
end

local function get_rules_path(node_modules_path, str)
  local config_parts = vim.split(str, "/")
  local rule_scope = config_parts[1]
  local rule_name = config_parts[2]

  local found_rules = vim.fs.find((rule_name or rule_scope) .. ".js", { path = node_modules_path, limit = math.huge })

  if vim.tbl_isempty(found_rules) then
    if vim.startswith(rule_scope, "@") then
      local found_dir =
        vim.fs.find("package.json", { path = vim.fs.joinpath(node_modules_path, rule_scope), limit = math.huge })
      if #found_dir > 0 then
        return found_dir[1]
      end
    end

    if rule_scope ~= nil and rule_name ~= nil then
      local found_dir = vim.fs.find("package.json", {
        path = vim.fs.joinpath(node_modules_path, "eslint-plugin-" .. rule_scope),
        limit = math.huge,
      })
      if #found_dir > 0 then
        return found_dir[1]
      end
    end

    return nil
  end

  if #found_rules > 1 then
    vim.ui.select(found_rules, {
      prompt = "Select rule",
      format_item = function(item)
        -- strip off absolute path, only keep relative path from root
        return vim.fn.fnamemodify(item, ":.")
      end,
    }, function(selected)
      if not selected then
        vim.notify("No rule selected", vim.log.levels.WARN)
        return
      end

      vim.cmd("edit " .. selected)
    end)

    return false
  end

  return found_rules[1]
end

local function get_eslint_path()
  local buf_dir = vim.fs.dirname(vim.api.nvim_buf_get_name(0))
  local root_dir = vim.fs.find({ ".git", "yarn.lock", "package-lock.json" }, { upward = true, path = buf_dir })
  if vim.tbl_isempty(root_dir) then
    vim.notify("No .git directory or yarn.lock or package-lock. found", vim.log.levels.WARN)
    return
  end

  local git_dir = root_dir[1]

  local node_modules = vim.fs.find(
    "node_modules",
    { upward = true, type = "directory", stop = git_dir, path = buf_dir, limit = math.huge }
  )

  if vim.tbl_isempty(node_modules) then
    vim.notify("No node_modules directory found", vim.log.levels.WARN)
    return
  end

  local cursor_row, cursor_col = unpack(vim.api.nvim_win_get_cursor(0))
  -- treesitter is 0 indexed
  cursor_row = cursor_row - 1

  local bufnr = vim.api.nvim_get_current_buf()
  local parser = vim.treesitter.get_parser(bufnr, vim.bo.filetype)
  local trees = parser:parse()
  local tree = trees[1]
  local root = tree:root()

  local cursor_node = root:descendant_for_range(cursor_row, cursor_col, cursor_row, cursor_col)

  if cursor_node == nil then
    vim.notify("Cursor was not within a node", vim.log.levels.WARN)
    return
  end

  local cursor_node_text = vim.treesitter.get_node_text(cursor_node, bufnr)

  local parent = cursor_node:parent()

  while parent ~= nil do
    local type = parent:type()

    if type == "pair" and parent:child_count() > 0 then
      local child = parent:child(0)
      if not child then
        vim.notify("No key found", vim.log.levels.WARN)
        return
      end

      -- if it's either ecma property_identifier or json key string
      if child:type() == "property_identifier" or child:type() == "string" then
        local eslint_key = vim.treesitter.get_node_text(child, bufnr)

        -- json key is a "string" node, so we need to remove the quotes
        if child:type() == "string" then
          eslint_key = string.gsub(eslint_key, '"', "")
        end

        if eslint_key == "extends" then
          for i = 1, #node_modules do
            local success_path, fallback_path = get_extends_path(node_modules[i], cursor_node_text)

            if success_path then
              return success_path
            end

            if i == #node_modules then
              local found = vim.fs.find("package.json", { path = fallback_path })
              if vim.tbl_isempty(found) then
                vim.notify("No package.json found for config: " .. cursor_node_text, vim.log.levels.WARN)
                return nil
              end

              vim.notify("No config found, defaulting to package.json for " .. cursor_node_text, vim.log.levels.INFO)
              return found[1]
            end
          end
        end

        if eslint_key == "plugins" then
          for i = 1, #node_modules do
            local plugin_path = get_plugins_path(node_modules[i], cursor_node_text)

            if plugin_path then
              return plugin_path
            end

            if i == #node_modules then
              vim.notify("No package.json found for plugin: " .. cursor_node_text, vim.log.levels.WARN)
              return nil
            end
          end
        end

        if eslint_key == "rules" then
          for i = 1, #node_modules do
            local rule_path = get_rules_path(node_modules[i], cursor_node_text)

            if rule_path == false then
              return nil
            end

            if rule_path then
              return rule_path
            end

            if i == #node_modules then
              vim.notify("No rule found for " .. cursor_node_text, vim.log.levels.WARN)
              return nil
            end
          end
        end
      end
    end
    parent = parent:parent()
  end
end

local function open_eslint_path()
  local eslint_path = get_eslint_path()

  if eslint_path then
    vim.cmd("edit " .. eslint_path)
  end
end

vim.keymap.set("n", "<leader>sfe", open_eslint_path, { desc = "Open eslint path" })
