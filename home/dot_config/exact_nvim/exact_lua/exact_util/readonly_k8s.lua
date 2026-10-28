local K8sSchema = {}
K8sSchema.schema_cache = {}
K8sSchema.default_version = nil

function K8sSchema.get_default_version()
  if K8sSchema.default_version then
    return K8sSchema.default_version
  end

  local kubectl_version = vim.fn.system("kubectl version --client --output=json")
  if vim.v.shell_error == 0 then
    local ok, data = pcall(vim.json.decode, kubectl_version)
    if ok and data.clientVersion and data.clientVersion.gitVersion then
      local v = data.clientVersion.gitVersion:match("^(v%d+%.%d+%.%d+)")
      if v then
        K8sSchema.default_version = v
        return v
      end
    end
  end

  K8sSchema.default_version = "master"
  return "master"
end

function K8sSchema.find_chart_root()
  local current_buf = vim.api.nvim_buf_get_name(0)
  if current_buf == "" then
    return nil
  end

  if current_buf:match("Chart%.yaml$") then
    return vim.fs.dirname(current_buf)
  end

  local root = vim.fs.find("Chart.yaml", {
    path = vim.fs.dirname(current_buf),
    upward = true,
    stop = vim.uv.os_homedir(),
  })[1]

  if root then
    return vim.fs.dirname(root)
  end
  return nil
end

function K8sSchema.get_target_version()
  local root = K8sSchema.find_chart_root()
  if root then
    local f = io.open(root .. "/Chart.yaml", "r")
    if f then
      local content = f:read("*a")
      f:close()

      -- Examples: ">= 1.20.0", "v1.24.0", "1.24.0-0"
      local kv = content:match("kubeVersion:%s*([^\n]+)")
      if kv then
        local major, minor, patch = kv:match("(%d+)%.(%d+)%.(%d+)")
        if major and minor and patch then
          return "v" .. major .. "." .. minor .. "." .. patch
        end
      end
    end
  end
  return K8sSchema.get_default_version()
end

function K8sSchema.get_base_url()
  local version = K8sSchema.get_target_version()
  return "https://raw.githubusercontent.com/yannh/kubernetes-json-schema/master/" .. version .. "-standalone-strict/"
end

function K8sSchema.show_in_split(title, schema)
  local content = vim.json.encode(schema)

  local formatted = vim.fn.system({ "jq", "." }, content)
  if vim.v.shell_error ~= 0 then
    formatted = content:gsub(",", ",\n"):gsub("{", "{\n"):gsub("}", "\n}")
  end

  local lines = vim.split(formatted, "\n")
  local original_win = vim.api.nvim_get_current_win()
  local schema_buf_name = "k8s-schema://" .. title

  local existing_win = nil
  local current_win_buf = nil

  for _, win in ipairs(vim.api.nvim_list_wins()) do
    if vim.api.nvim_win_is_valid(win) then
      local buf = vim.api.nvim_win_get_buf(win)
      if vim.api.nvim_buf_is_valid(buf) then
        local name = vim.api.nvim_buf_get_name(buf)
        local is_schema = false
        local status, result = pcall(vim.api.nvim_buf_get_var, buf, "is_k8s_schema_buffer")
        if status and result then
          is_schema = true
        elseif name:match("k8s%-schema://") then
          is_schema = true
        end

        if is_schema then
          existing_win = win
          current_win_buf = buf
          break
        end
      end
    end
  end

  local target_buf = nil

  local function names_match(buf_name, target_name)
    return buf_name == target_name or buf_name:match("/" .. vim.pesc(target_name) .. "$")
  end

  if current_win_buf and vim.api.nvim_buf_is_valid(current_win_buf) then
    local name = vim.api.nvim_buf_get_name(current_win_buf)
    if names_match(name, schema_buf_name) then
      target_buf = current_win_buf
    end
  end

  if not target_buf then
    for _, buf in ipairs(vim.api.nvim_list_bufs()) do
      if vim.api.nvim_buf_is_valid(buf) then
        local name = vim.api.nvim_buf_get_name(buf)
        if names_match(name, schema_buf_name) then
          target_buf = buf
          break
        end
      end
    end
  end

  if not target_buf then
    local new_buf = vim.api.nvim_create_buf(false, true)
    local ok, _ = pcall(vim.api.nvim_buf_set_name, new_buf, schema_buf_name)

    if ok then
      target_buf = new_buf
    else
      vim.api.nvim_buf_delete(new_buf, { force = true })

      for _, buf in ipairs(vim.api.nvim_list_bufs()) do
        if vim.api.nvim_buf_is_valid(buf) then
          local name = vim.api.nvim_buf_get_name(buf)
          if names_match(name, schema_buf_name) then
            target_buf = buf
            break
          end
        end
      end

      if not target_buf then
        -- Fallback: Just create an unnamed buffer to avoid erroring,
        -- though reuse won't work perfectly for this specific edge case.
        target_buf = vim.api.nvim_create_buf(false, true)
        pcall(vim.api.nvim_buf_set_name, target_buf, schema_buf_name .. "-" .. os.time())
      end
    end

    vim.api.nvim_set_option_value("buftype", "nofile", { buf = target_buf })
    vim.api.nvim_set_option_value("bufhidden", "wipe", { buf = target_buf })
    vim.api.nvim_set_option_value("buflisted", false, { buf = target_buf })
    vim.api.nvim_set_option_value("swapfile", false, { buf = target_buf })
    vim.api.nvim_set_option_value("filetype", "json", { buf = target_buf })
  end

  vim.api.nvim_buf_set_var(target_buf, "is_k8s_schema_buffer", true)

  vim.api.nvim_set_option_value("modifiable", true, { buf = target_buf })
  vim.api.nvim_buf_set_lines(target_buf, 0, -1, false, lines)
  vim.api.nvim_set_option_value("modifiable", false, { buf = target_buf })

  vim.keymap.set("n", "q", "<cmd>close<cr>", { buffer = target_buf, desc = "Close schema" })

  if existing_win and vim.api.nvim_win_is_valid(existing_win) then
    local win_buf = vim.api.nvim_win_get_buf(existing_win)
    if win_buf ~= target_buf then
      vim.api.nvim_win_set_buf(existing_win, target_buf)
    end
    vim.api.nvim_set_option_value("wrap", true, { win = existing_win })

    if current_win_buf and current_win_buf ~= target_buf and vim.api.nvim_buf_is_valid(current_win_buf) then
      local is_schema = false
      local status, result = pcall(vim.api.nvim_buf_get_var, current_win_buf, "is_k8s_schema_buffer")
      if status and result then
        is_schema = true
      else
        local name = vim.api.nvim_buf_get_name(current_win_buf)
        if name:match("k8s%-schema://") then
          is_schema = true
        end
      end

      if is_schema then
        pcall(vim.api.nvim_buf_delete, current_win_buf, { force = true })
      end
    end
  else
    vim.cmd("vsplit")
    local new_win = vim.api.nvim_get_current_win()
    vim.api.nvim_win_set_buf(new_win, target_buf)
    vim.api.nvim_set_option_value("wrap", true, { win = new_win })
  end

  if vim.api.nvim_win_is_valid(original_win) then
    vim.api.nvim_set_current_win(original_win)
  end
end

function K8sSchema.get_yaml_path()
  local bufnr = vim.api.nvim_get_current_buf()
  local cursor_line = vim.api.nvim_win_get_cursor(0)[1]

  local start_line = 1
  for i = cursor_line, 1, -1 do
    local line = vim.api.nvim_buf_get_lines(bufnr, i - 1, i, false)[1]
    if line and line:match("^%-%-%-") then
      start_line = i + 1
      break
    end
  end

  local lines = vim.api.nvim_buf_get_lines(bufnr, start_line - 1, cursor_line, false)

  local path = {}
  local indent_stack = { { indent = -1, key = nil, is_list = false } }

  for _, line in ipairs(lines) do
    if line:match("^%s*$") or line:match("^%s*#") or line:match("^%s*{{") then
      goto continue
    end

    local raw_indent = #(line:match("^(%s*)") or "")
    local is_list_item = line:match("^%s*%-") ~= nil

    local key = line:match("^%s*%-?%s*([%w_]+)%s*:")

    if key then
      -- For list items "- key:", normalize indent to make siblings equal
      -- "- name:" at indent 8 and "image:" at indent 10 should be treated as same level
      local indent = raw_indent
      if is_list_item then
        -- The "- " takes 2 chars, so content after it is logically at raw_indent + 2
        indent = raw_indent + 2
      end

      while #indent_stack > 1 and indent_stack[#indent_stack].indent >= indent do
        table.remove(indent_stack)
      end

      table.insert(indent_stack, { indent = indent, key = key, is_list = is_list_item })
    elseif is_list_item then
      local indent = raw_indent + 2
      while #indent_stack > 1 and indent_stack[#indent_stack].indent >= indent do
        table.remove(indent_stack)
      end
    end

    ::continue::
  end

  for i = 2, #indent_stack do
    local entry = indent_stack[i]
    if entry.key then
      table.insert(path, entry.key)
    end
  end

  return path
end

function K8sSchema.get_resource_type()
  local cursor_line = vim.api.nvim_win_get_cursor(0)[1]
  local line_count = vim.api.nvim_buf_line_count(0)

  local start_line = 1
  for i = cursor_line, 1, -1 do
    local line = vim.api.nvim_buf_get_lines(0, i - 1, i, false)[1]
    if line and line:match("^%-%-%-") then
      start_line = i + 1
      break
    end
  end

  local end_line = line_count
  for i = cursor_line + 1, line_count do
    local line = vim.api.nvim_buf_get_lines(0, i - 1, i, false)[1]
    if line and line:match("^%-%-%-") then
      end_line = i - 1
      break
    end
  end

  local lines = vim.api.nvim_buf_get_lines(0, start_line - 1, end_line, false)
  local found_kind = { val = nil, indent = 999 }
  local found_api = { val = nil, indent = 999 }

  for _, line in ipairs(lines) do
    if not line:match("^%s*#") then
      local current_indent = #(line:match("^(%s*)") or "")

      local api = line:match("^%s*apiVersion:%s*[\"']?([%w%.%/]+)[\"']?")
      if api and current_indent < found_api.indent then
        found_api = { val = api, indent = current_indent }
      end

      local k = line:match("^%s*kind:%s*[\"']?(%w+)[\"']?")
      if k and current_indent < found_kind.indent then
        found_kind = { val = k, indent = current_indent }
      end
    end
  end

  local kind = found_kind.val
  local api_version = found_api.val

  if kind and not api_version then
    local defaults = {
      Deployment = "apps/v1",
      Service = "v1",
      Pod = "v1",
      ConfigMap = "v1",
      Secret = "v1",
      Ingress = "networking.k8s.io/v1",
      StatefulSet = "apps/v1",
      DaemonSet = "apps/v1",
      Job = "batch/v1",
      CronJob = "batch/v1",
      ServiceAccount = "v1",
      Role = "rbac.authorization.k8s.io/v1",
      ClusterRole = "rbac.authorization.k8s.io/v1",
      RoleBinding = "rbac.authorization.k8s.io/v1",
      ClusterRoleBinding = "rbac.authorization.k8s.io/v1",
      PersistentVolume = "v1",
      PersistentVolumeClaim = "v1",
      Namespace = "v1",
      HorizontalPodAutoscaler = "autoscaling/v2",
      NetworkPolicy = "networking.k8s.io/v1",
      PodDisruptionBudget = "policy/v1",
      StorageClass = "storage.k8s.io/v1",
    }
    api_version = defaults[kind]
  end

  return api_version, kind
end

function K8sSchema.get_schema_filename(api_version, kind)
  if not api_version or not kind then
    return nil
  end

  local kind_lower = kind:lower()

  local group, version = api_version:match("([%w%.]+)/(%w+)")
  if not group then
    version = api_version
    return kind_lower .. "-" .. version .. ".json"
  end

  local group_map = {
    ["apps"] = "apps",
    ["batch"] = "batch",
    ["networking.k8s.io"] = "networking",
    ["rbac.authorization.k8s.io"] = "rbac",
    ["policy"] = "policy",
    ["autoscaling"] = "autoscaling",
  }

  local group_prefix = group_map[group] or group:gsub("%.k8s%.io", ""):gsub("%.", "-")
  return kind_lower .. "-" .. group_prefix .. "-" .. version .. ".json"
end

function K8sSchema.fetch_schema(filename, callback)
  if K8sSchema.schema_cache[filename] then
    callback(K8sSchema.schema_cache[filename])
    return
  end

  local function try_fetch(version_url, is_fallback)
    local url = version_url .. filename
    vim.system(
      { "curl", "-sfL", url },
      { text = true },
      vim.schedule_wrap(function(result)
        if result.code == 0 and result.stdout and result.stdout ~= "" then
          local ok, schema = pcall(vim.json.decode, result.stdout)
          if ok then
            K8sSchema.schema_cache[filename] = schema
            callback(schema)
            return
          end
        end

        if not is_fallback then
          local default_ver = K8sSchema.get_default_version()
          local default_url = "https://raw.githubusercontent.com/yannh/kubernetes-json-schema/master/"
            .. default_ver
            .. "-standalone-strict/"
          -- Avoid infinite loop if target WAS already default
          if version_url ~= default_url then
            vim.notify("Schema not found for target version, falling back to " .. default_ver, vim.log.levels.INFO)
            try_fetch(default_url, true)
            return
          end
        end

        callback(nil)
      end)
    )
  end

  try_fetch(K8sSchema.get_base_url(), false)
end

function K8sSchema.has_type(schema, type_name)
  local t = schema.type
  if t == type_name then
    return true
  end
  if type(t) == "table" then
    for _, v in ipairs(t) do
      if v == type_name then
        return true
      end
    end
  end
  return false
end

function K8sSchema.navigate_schema(schema, path, callback, current_index, root_schema)
  current_index = current_index or 1
  root_schema = root_schema or schema

  if current_index > #path then
    callback(schema, table.concat(path, "."))
    return
  end

  local key = path[current_index]
  local prop_schema = nil

  if schema.properties and schema.properties[key] then
    prop_schema = schema.properties[key]
  elseif schema.additionalProperties and type(schema.additionalProperties) == "table" then
    prop_schema = schema.additionalProperties
  end

  if prop_schema then
    if prop_schema["$ref"] then
      local ref = prop_schema["$ref"]

      if ref:sub(1, 1) == "#" then
        local def_name = ref:match("#/definitions/(.+)")
        if def_name and root_schema.definitions and root_schema.definitions[def_name] then
          K8sSchema.navigate_schema(root_schema.definitions[def_name], path, callback, current_index + 1, root_schema)
          return
        end
      end

      local ref_type = ref:match("%.([%w]+)$")
      if ref_type then
        local ref_filename = ref_type:lower() .. "-v1.json"
        K8sSchema.fetch_schema(ref_filename, function(ref_schema)
          if ref_schema then
            K8sSchema.navigate_schema(ref_schema, path, callback, current_index + 1, ref_schema)
          else
            ref_filename = ref_type:lower() .. ".json"
            K8sSchema.fetch_schema(ref_filename, function(ref_schema2)
              if ref_schema2 then
                K8sSchema.navigate_schema(ref_schema2, path, callback, current_index + 1, ref_schema2)
              else
                callback(nil, "Could not resolve $ref: " .. ref)
              end
            end)
          end
        end)
        return
      end
    end

    if K8sSchema.has_type(prop_schema, "array") and prop_schema.items then
      local items = prop_schema.items
      if items["$ref"] then
        local ref = items["$ref"]

        if ref:sub(1, 1) == "#" then
          local def_name = ref:match("#/definitions/(.+)")
          if def_name and root_schema.definitions and root_schema.definitions[def_name] then
            K8sSchema.navigate_schema(root_schema.definitions[def_name], path, callback, current_index + 1, root_schema)
            return
          end
        end

        local ref_type = ref:match("%.([%w]+)$")
        if ref_type then
          local ref_filename = ref_type:lower() .. "-v1.json"
          K8sSchema.fetch_schema(ref_filename, function(ref_schema)
            if ref_schema then
              K8sSchema.navigate_schema(ref_schema, path, callback, current_index + 1, ref_schema)
            else
              callback(nil, "Could not resolve array item $ref: " .. ref)
            end
          end)
          return
        end
      else
        K8sSchema.navigate_schema(items, path, callback, current_index + 1, root_schema)
        return
      end
    end

    if current_index == #path then
      callback(prop_schema, table.concat(path, "."))
    else
      K8sSchema.navigate_schema(prop_schema, path, callback, current_index + 1, root_schema)
    end
    return
  end

  local keys = {}
  if schema.properties then
    for k, _ in pairs(schema.properties) do
      table.insert(keys, k)
    end
  end

  local debug_info = string.format(
    "Property '%s' not found at path: %s. Available keys: %s",
    key,
    table.concat(path, ".", 1, current_index),
    table.concat(keys, ", ")
  )

  callback(nil, debug_info)
end

function K8sSchema.show_property()
  local buf_name = vim.api.nvim_buf_get_name(0)
  if buf_name:match("Chart%.yaml$") or buf_name:match("Chart%.yml$") then
    vim.notify("K8s resource schema lookup is not supported for Chart.yaml files", vim.log.levels.INFO)
    return
  end

  local path = K8sSchema.get_yaml_path()
  if #path == 0 then
    vim.notify("Could not determine YAML path", vim.log.levels.WARN)
    return
  end

  local api_version, kind = K8sSchema.get_resource_type()
  if not api_version or not kind then
    vim.notify("Could not find apiVersion/kind in buffer", vim.log.levels.WARN)
    return
  end

  local schema_filename = K8sSchema.get_schema_filename(api_version, kind)
  if not schema_filename then
    vim.notify("Could not determine schema filename", vim.log.levels.WARN)
    return
  end

  local display_path = kind .. "." .. table.concat(path, ".")

  K8sSchema.fetch_schema(schema_filename, function(schema)
    if not schema then
      vim.notify("Could not fetch schema: " .. schema_filename, vim.log.levels.ERROR)
      return
    end

    K8sSchema.navigate_schema(schema, path, function(result, result_path)
      if result then
        K8sSchema.show_in_split(result_path or display_path, result)
      else
        vim.notify(result_path or "Schema property not found", vim.log.levels.ERROR)
      end
    end, 1, schema)
  end)
end

return K8sSchema
