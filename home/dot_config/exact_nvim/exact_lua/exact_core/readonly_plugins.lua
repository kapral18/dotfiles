local M = {}

---@class core.plugins.Entry
---@field name string
---@field index number
---@field specs table[]
---@field deps table<string, boolean>
---@field src string|nil
---@field dir string|nil
---@field enabled boolean

local function notify_err(msg)
  vim.schedule(function()
    vim.notify(msg, vim.log.levels.ERROR)
  end)
end

local function as_list(value)
  if value == nil then
    return {}
  end
  if type(value) == "table" then
    if vim.islist(value) then
      return value
    end
    return { value }
  end
  return { value }
end

local function repo_to_name(repo)
  if type(repo) ~= "string" or repo == "" then
    return nil
  end
  local name = repo:match("/([^/]+)$") or repo
  return name:gsub("%.git$", "")
end

local function repo_to_src(repo)
  if type(repo) ~= "string" or repo == "" then
    return nil
  end
  if repo:match("^[%a][%w+.-]*://") or repo:match("^git@") or repo:match("^gh:") then
    return repo
  end
  if repo:match("^[%w%._-]+/[%w%._-]+$") then
    return "https://github.com/" .. repo .. ".git"
  end
  return repo
end

local function normalize_spec(spec)
  if type(spec) == "string" then
    return { spec }
  end
  if type(spec) ~= "table" then
    return nil
  end
  return spec
end

local function eval_gate(value, default)
  if value == nil then
    return default
  end
  if type(value) == "function" then
    local ok, result = pcall(value)
    if not ok then
      return false
    end
    return result and true or false
  end
  return value and true or false
end

local function key_opts_from_spec(spec)
  local opts = {
    desc = spec.desc,
    expr = spec.expr,
    nowait = spec.nowait,
    silent = spec.silent,
  }

  if spec.noremap ~= nil then
    opts.noremap = spec.noremap
  elseif spec.remap ~= nil then
    opts.remap = spec.remap
  elseif type(spec[2]) == "string" and spec[2]:match("^<Plug>") then
    -- <Plug> mappings usually need remap semantics.
    opts.remap = true
  end

  return opts
end

local function normalize_key_specs(specs, plugin_spec)
  if type(specs) == "function" then
    local ok, resolved = pcall(specs, plugin_spec, {})
    if not ok then
      notify_err("Failed to resolve key specs for " .. (plugin_spec.name or plugin_spec[1] or "<unknown>"))
      return {}
    end
    specs = resolved
  end

  local normalized = {}
  for _, spec in ipairs(as_list(specs)) do
    if type(spec) == "table" then
      local lhs = spec.lhs or spec[1]
      local rhs = spec.rhs or spec[2]
      if lhs and rhs ~= nil and eval_gate(spec.enabled, true) then
        normalized[#normalized + 1] = {
          lhs = lhs,
          rhs = rhs,
          mode = spec.mode or "n",
          ft = spec.ft,
          opts = key_opts_from_spec(spec),
        }
      end
    end
  end
  return normalized
end

local function derive_module_candidates(entry)
  local seen = {}
  local out = {}

  local function add(value)
    if type(value) ~= "string" or value == "" then
      return
    end
    if seen[value] then
      return
    end
    seen[value] = true
    out[#out + 1] = value
  end

  local base = entry.name
  add(base)
  if base then
    add(base:gsub("%.nvim$", ""))
    add(base:gsub("%.vim$", ""))
    add(base:gsub("^nvim%-", ""))
    add(base:gsub("^vim%-", ""))
    add(base:gsub("%-", "_"))
  end

  return out
end

local function run_auto_setup(entry, opts)
  if type(opts) ~= "table" then
    return
  end

  for _, mod_name in ipairs(derive_module_candidates(entry)) do
    local ok_mod, mod = pcall(require, mod_name)
    if ok_mod and type(mod) == "table" and type(mod.setup) == "function" then
      local ok_setup, err = pcall(mod.setup, opts)
      if not ok_setup then
        notify_err("Failed setup() for " .. entry.name .. ": " .. tostring(err))
      end
      return
    end
  end
end

local function run_build(build, path)
  if type(build) == "function" then
    -- Manager-style function builds often assume manager-specific lifecycle.
    -- Skip them under vim.pack to avoid startup/install failures.
    return
  end

  if type(build) ~= "string" or build == "" then
    return
  end

  if build:sub(1, 1) == ":" then
    -- Ex-command builds are also manager-specific; skip for now.
    return
  end

  local result = vim.system({ "/bin/sh", "-c", build }, { cwd = path, text = true }):wait()
  if result.code ~= 0 then
    notify_err("Build shell command failed (" .. build .. "): " .. ((result.stderr or "exit ") .. result.code))
  end
end

local function flatten_specs(module_names)
  local entries = {} ---@type table<string, core.plugins.Entry>
  local order = 0

  local function get_or_create(name)
    local entry = entries[name]
    if entry then
      return entry
    end
    order = order + 1
    entry = {
      name = name,
      index = order,
      specs = {},
      deps = {},
      src = nil,
      dir = nil,
      enabled = true,
    }
    entries[name] = entry
    return entry
  end

  local function add_spec(spec)
    spec = normalize_spec(spec)
    if not spec then
      return nil
    end

    local source = spec.src or spec[1]
    local name = spec.name or repo_to_name(source)
    if not name and type(spec.dir) == "string" then
      name = vim.fs.basename(spec.dir)
    end
    if not name then
      return nil
    end

    local entry = get_or_create(name)
    entry.specs[#entry.specs + 1] = spec

    if not entry.src and type(source) == "string" then
      entry.src = repo_to_src(source)
    end
    if not entry.dir and type(spec.dir) == "string" then
      entry.dir = spec.dir
    end

    if not eval_gate(spec.enabled, true) or not eval_gate(spec.cond, true) then
      entry.enabled = false
    end

    local deps = as_list(spec.dependencies)
    for _, dep in ipairs(deps) do
      if type(dep) == "string" then
        local dep_name = repo_to_name(dep)
        if dep_name then
          entry.deps[dep_name] = true
          if dep:find("/") then
            add_spec({ dep })
          end
        end
      elseif type(dep) == "table" then
        local dep_entry = add_spec(dep)
        local is_optional_dep = dep and (dep.optional == true or dep.opt == true)
        if dep_entry and not is_optional_dep then
          entry.deps[dep_entry.name] = true
        end
      end
    end

    return entry
  end

  for _, module_name in ipairs(module_names) do
    local ok, mod = pcall(require, module_name)
    if not ok then
      notify_err("Failed loading plugin module: " .. module_name)
    else
      for _, spec in ipairs(as_list(mod)) do
        add_spec(spec)
      end
    end
  end

  return entries
end

local function resolve_opts(entry)
  local opts = {}
  for _, spec in ipairs(entry.specs) do
    local spec_opts = spec.opts
    if type(spec_opts) == "function" then
      local ok, result = pcall(spec_opts, spec, opts)
      if not ok then
        notify_err("opts() failed for " .. entry.name)
      elseif result ~= nil then
        opts = result
      end
    elseif type(spec_opts) == "table" then
      opts = vim.tbl_deep_extend("force", opts, vim.deepcopy(spec_opts))
    end
  end
  return opts
end

local function ordered_entries(entries)
  local keys = {}
  for name in pairs(entries) do
    keys[#keys + 1] = name
  end
  table.sort(keys, function(a, b)
    return entries[a].index < entries[b].index
  end)

  local out = {}
  local visiting = {}
  local visited = {}

  local function visit(name)
    if visited[name] then
      return
    end
    if visiting[name] then
      return
    end
    visiting[name] = true
    local entry = entries[name]
    for dep in pairs(entry.deps) do
      if entries[dep] then
        visit(dep)
      end
    end
    visiting[name] = nil
    visited[name] = true
    out[#out + 1] = entry
  end

  for _, name in ipairs(keys) do
    visit(name)
  end

  return out
end

local function normalize_pack_version(version)
  if version == nil or version == false then
    return nil
  end
  if type(version) ~= "string" then
    return version
  end

  local v = vim.trim(version)
  if v == "" or v == "*" then
    return nil
  end

  if v:find("[%^~><=]") then
    local ok, range = pcall(vim.version.range, v)
    if ok then
      return range
    end
  end

  return v
end

function M.setup(module_names)
  local entries = flatten_specs(module_names)
  local sorted = ordered_entries(entries)

  local build_hooks = {}
  local pack_specs = {}

  for _, entry in ipairs(sorted) do
    if entry.enabled then
      for _, spec in ipairs(entry.specs) do
        if type(spec.init) == "function" then
          local ok, err = pcall(spec.init, spec)
          if not ok then
            notify_err("init() failed for " .. entry.name .. ": " .. tostring(err))
          end
        end

        if spec.build ~= nil then
          build_hooks[entry.name] = build_hooks[entry.name] or {}
          build_hooks[entry.name][#build_hooks[entry.name] + 1] = spec.build
        end
      end

      if entry.src then
        local version = nil
        for _, spec in ipairs(entry.specs) do
          if type(spec.commit) == "string" and spec.commit ~= "" then
            version = spec.commit
          elseif type(spec.tag) == "string" and spec.tag ~= "" then
            version = spec.tag
          elseif type(spec.branch) == "string" and spec.branch ~= "" then
            version = spec.branch
          elseif spec.version ~= nil then
            version = spec.version
          end
        end

        local pack_spec = { src = entry.src, name = entry.name }
        version = normalize_pack_version(version)
        if version ~= nil then
          pack_spec.version = version
        end
        pack_specs[#pack_specs + 1] = pack_spec
      end
    end
  end

  local entry_meta = {}
  local entry_state = {}
  local command_wrappers = {}
  local load_entry

  local function entry_name_complete(arglead)
    local names = {}
    for name, entry in pairs(entries) do
      if entry.enabled and (arglead == "" or name:find("^" .. vim.pesc(arglead))) then
        names[#names + 1] = name
      end
    end
    table.sort(names)
    return names
  end

  for _, entry in ipairs(sorted) do
    entry_state[entry.name] = { loading = false, configured = false, loaded_at = nil, loaded_by = nil, load_count = 0 }
    if entry.enabled then
      local meta = {
        cmds = {},
        events = {},
        fts = {},
        keys = {},
        has_keys = false,
        defer = false,
      }
      local seen_cmd, seen_event, seen_ft = {}, {}, {}
      local force_start = false

      for _, spec in ipairs(entry.specs) do
        if spec.lazy == false then
          force_start = true
        end

        for _, cmd in ipairs(as_list(spec.cmd)) do
          if type(cmd) == "string" and cmd ~= "" and not seen_cmd[cmd] then
            seen_cmd[cmd] = true
            meta.cmds[#meta.cmds + 1] = cmd
          end
        end

        for _, ev in ipairs(as_list(spec.event)) do
          local ev_name, ev_pattern
          if type(ev) == "string" then
            ev_name = ev
          elseif type(ev) == "table" then
            ev_name = ev.event or ev[1]
            ev_pattern = ev.pattern
          end
          if type(ev_name) == "string" and ev_name ~= "" then
            local key = ev_name .. "\0" .. tostring(ev_pattern or "")
            if not seen_event[key] then
              seen_event[key] = true
              meta.events[#meta.events + 1] = { event = ev_name, pattern = ev_pattern }
            end
          end
        end

        for _, ft in ipairs(as_list(spec.ft)) do
          if type(ft) == "string" and ft ~= "" and not seen_ft[ft] then
            seen_ft[ft] = true
            meta.fts[#meta.fts + 1] = ft
          end
        end

        local key_specs = normalize_key_specs(spec.keys, spec)
        if #key_specs > 0 then
          meta.has_keys = true
          vim.list_extend(meta.keys, key_specs)
        end
      end

      meta.defer = not force_start and (#meta.cmds > 0 or #meta.events > 0 or #meta.fts > 0 or meta.has_keys)
      entry_meta[entry.name] = meta
    end
  end

  require("core.pack_dashboard").setup()

  vim.api.nvim_create_autocmd("PackChanged", {
    callback = function(ev)
      local data = ev.data or {}
      if data.kind ~= "install" and data.kind ~= "update" then
        return
      end
      local name = data.spec and data.spec.name
      if not name or not build_hooks[name] then
        return
      end

      pcall(vim.cmd.packadd, name)
      for _, build in ipairs(build_hooks[name]) do
        run_build(build, data.path)
      end
    end,
  })

  if #pack_specs > 0 then
    vim.pack.add(pack_specs, { confirm = false, load = false })
  end

  local function apply_entry(entry, reason)
    local state = entry_state[entry.name]
    if not state or state.configured or state.loading then
      return true
    end

    state.loading = true

    for dep_name in pairs(entry.deps) do
      local dep = entries[dep_name]
      if dep and dep.enabled then
        load_entry(dep_name, "dependency:" .. entry.name)
      end
    end

    if entry.src then
      pcall(vim.cmd.packadd, entry.name)
    end

    local opts = resolve_opts(entry)
    local ran_config = false
    for _, spec in ipairs(entry.specs) do
      if type(spec.config) == "function" then
        local ok, err = pcall(spec.config, spec, opts)
        if not ok then
          notify_err("config() failed for " .. entry.name .. ": " .. tostring(err))
        end
        ran_config = true
      end
    end
    if not ran_config then
      run_auto_setup(entry, opts)
    end

    state.loading = false
    state.configured = true
    state.loaded_at = os.date("%H:%M:%S")
    state.loaded_by = reason or "unknown"
    state.load_count = (state.load_count or 0) + 1
    return true
  end

  load_entry = function(name, reason)
    local entry = entries[name]
    if not entry or not entry.enabled then
      return false
    end
    return apply_entry(entry, reason)
  end

  local function exec_mapped_rhs(key)
    if type(key.rhs) == "function" then
      return key.rhs()
    end
    if type(key.rhs) ~= "string" then
      return nil
    end
    if key.opts and key.opts.expr then
      return key.rhs
    end
    vim.api.nvim_feedkeys(vim.keycode(key.rhs), "m", false)
    return nil
  end

  local function map_key_trigger(entry_name, key)
    local map_opts = vim.deepcopy(key.opts)
    local rhs = function()
      load_entry(entry_name, "key:" .. tostring(key.lhs))
      return exec_mapped_rhs(key)
    end

    if key.ft then
      local patterns = type(key.ft) == "table" and key.ft or { key.ft }
      vim.api.nvim_create_autocmd("FileType", {
        pattern = patterns,
        callback = function(args)
          local buf_opts = vim.deepcopy(map_opts)
          buf_opts.buffer = args.buf
          vim.keymap.set(key.mode, key.lhs, rhs, buf_opts)
        end,
      })
    else
      vim.keymap.set(key.mode, key.lhs, rhs, map_opts)
    end
  end

  local function register_cmd_trigger(entry_name, cmd_name)
    if command_wrappers[cmd_name] then
      return
    end
    command_wrappers[cmd_name] = true

    vim.api.nvim_create_user_command(cmd_name, function(ctx)
      pcall(vim.api.nvim_del_user_command, cmd_name)
      load_entry(entry_name, "cmd:" .. cmd_name)

      local ex = cmd_name
      if ctx.range and ctx.range > 0 then
        ex = string.format("%d,%d%s", ctx.line1, ctx.line2, ex)
      end
      if ctx.bang then
        ex = ex .. "!"
      end
      if ctx.args and ctx.args ~= "" then
        ex = ex .. " " .. ctx.args
      end
      vim.cmd(ex)
    end, {
      nargs = "*",
      bang = true,
      range = true,
      desc = "Load plugin and execute " .. cmd_name,
    })
  end

  local function register_event_trigger(entry_name, event_item)
    vim.api.nvim_create_autocmd(event_item.event, {
      pattern = event_item.pattern,
      once = true,
      callback = function()
        load_entry(entry_name, "event:" .. event_item.event)
      end,
    })
  end

  local function register_ft_trigger(entry_name, fts)
    vim.api.nvim_create_autocmd("FileType", {
      pattern = fts,
      callback = function()
        load_entry(entry_name, "ft")
      end,
    })
  end

  local function trigger_summary(meta)
    local parts = {}
    if #meta.cmds > 0 then
      parts[#parts + 1] = "cmd(" .. table.concat(meta.cmds, ",") .. ")"
    end
    if #meta.events > 0 then
      local events = {}
      for _, ev in ipairs(meta.events) do
        if ev.pattern then
          events[#events + 1] = ev.event .. ":" .. tostring(ev.pattern)
        else
          events[#events + 1] = ev.event
        end
      end
      parts[#parts + 1] = "event(" .. table.concat(events, ",") .. ")"
    end
    if #meta.fts > 0 then
      parts[#parts + 1] = "ft(" .. table.concat(meta.fts, ",") .. ")"
    end
    if meta.has_keys then
      parts[#parts + 1] = "keys"
    end
    if #parts == 0 then
      return "startup"
    end
    return table.concat(parts, " ")
  end

  vim.api.nvim_create_user_command("PackLoad", function(ctx)
    local name = vim.trim(ctx.args or "")
    if name == "" then
      vim.notify("Usage: PackLoad <plugin-name>", vim.log.levels.WARN)
      return
    end
    local entry = entries[name]
    if not entry or not entry.enabled then
      vim.notify("Unknown or disabled plugin: " .. name, vim.log.levels.ERROR)
      return
    end
    local was_loaded = entry_state[name] and entry_state[name].configured
    load_entry(name, "manual:PackLoad")
    local state = entry_state[name]
    if was_loaded then
      vim.notify(name .. " already loaded", vim.log.levels.INFO)
    else
      vim.notify(string.format("%s loaded (%s)", name, state and state.loaded_by or "manual"), vim.log.levels.INFO)
    end
  end, {
    nargs = 1,
    complete = entry_name_complete,
    desc = "Force-load one deferred plugin by name",
  })

  vim.api.nvim_create_user_command("PackTrace", function(ctx)
    local filter = vim.trim(ctx.args or "")
    local lines = {
      "vim.pack trace",
      "status | plugin | loaded_by | loaded_at | count | triggers",
      "",
    }

    for _, entry in ipairs(sorted) do
      if entry.enabled and (filter == "" or entry.name == filter) then
        local state = entry_state[entry.name] or {}
        local meta = entry_meta[entry.name] or { cmds = {}, events = {}, fts = {}, has_keys = false }
        local status = state.configured and "loaded " or "defer  "
        local loaded_by = state.loaded_by or "-"
        local loaded_at = state.loaded_at or "-"
        local count = tostring(state.load_count or 0)
        lines[#lines + 1] = string.format(
          "%s | %s | %s | %s | %s | %s",
          status,
          entry.name,
          loaded_by,
          loaded_at,
          count,
          trigger_summary(meta)
        )
      end
    end

    if #lines == 3 then
      lines[#lines + 1] = "No matching enabled plugin: " .. filter
    end

    local bufnr = vim.api.nvim_create_buf(false, true)
    vim.bo[bufnr].buftype = "nofile"
    vim.bo[bufnr].bufhidden = "wipe"
    vim.bo[bufnr].buflisted = false
    vim.bo[bufnr].swapfile = false
    vim.bo[bufnr].modifiable = true
    vim.api.nvim_buf_set_lines(bufnr, 0, -1, false, lines)
    vim.bo[bufnr].modifiable = false
    vim.bo[bufnr].filetype = "packtrace"
    local ui = vim.api.nvim_list_uis()[1]
    if ui then
      local width = math.max(80, math.floor(ui.width * 0.9))
      local height = math.max(12, math.min(#lines + 2, math.floor(ui.height * 0.8)))
      local row = math.floor((ui.height - height) / 2)
      local col = math.floor((ui.width - width) / 2)
      local win = vim.api.nvim_open_win(bufnr, true, {
        relative = "editor",
        style = "minimal",
        border = "rounded",
        title = " Pack Trace ",
        title_pos = "center",
        width = width,
        height = height,
        row = row,
        col = col,
      })
      vim.wo[win].cursorline = true
    else
      vim.cmd.sbuffer({ bufnr })
    end
    vim.keymap.set("n", "q", "<cmd>close<cr>", { buffer = bufnr, nowait = true, silent = true })
    vim.keymap.set("n", "<Esc>", "<cmd>close<cr>", { buffer = bufnr, nowait = true, silent = true })
  end, {
    nargs = "?",
    complete = entry_name_complete,
    desc = "Show deferred/loaded plugin trace table",
  })

  for _, entry in ipairs(sorted) do
    if entry.enabled then
      local meta = entry_meta[entry.name] or { cmds = {}, events = {}, fts = {}, keys = {}, defer = false }

      for _, key in ipairs(meta.keys) do
        map_key_trigger(entry.name, key)
      end

      if meta.defer then
        for _, cmd_name in ipairs(meta.cmds) do
          register_cmd_trigger(entry.name, cmd_name)
        end
        for _, event_item in ipairs(meta.events) do
          register_event_trigger(entry.name, event_item)
        end
        if #meta.fts > 0 then
          register_ft_trigger(entry.name, meta.fts)
        end
      else
        load_entry(entry.name, "startup")
      end
    end
  end
end

return M
