local M = {}

M.pack_report_cache = {
  plugins = {},
  updated_at = nil,
  mode = nil,
  last_online_at = nil,
  last_offline_at = nil,
  last_applied_at = nil,
  last_applied_count = 0,
  last_check_counts = nil,
}

M.dashboard_ui_cache = {
  filter_mode = "all",
  sort_mode = "status",
  search_text = nil,
  selected_names = {},
}

M.persisted_state_loaded = false
M.declared_names_cache = {}
M.declared_versions_cache = {}
M.version_flags_cache = {}
M.version_flags_scan_running = false
M.version_flags_scanned = false

local function persisted_state_path()
  return vim.fn.stdpath("state") .. "/pack_dashboard_state.json"
end

function M.persisted_state_path()
  return persisted_state_path()
end

-- Record the set of plugin names declared by the active plugin specs so the
-- dashboard can distinguish "managed" packs from on-disk orphans. Accepts
-- either an array of names or a set (`name = true`). Calling with `nil` or a
-- non-table resets the cache to empty (which disables orphan flagging).
function M.set_declared_plugin_names(names)
  if type(names) ~= "table" then
    M.declared_names_cache = {}
    return
  end
  local normalized = {}
  if vim.islist(names) then
    for _, n in ipairs(names) do
      if type(n) == "string" and n ~= "" then
        normalized[n] = true
      end
    end
  else
    for n, v in pairs(names) do
      if type(n) == "string" and n ~= "" and v then
        normalized[n] = true
      end
    end
  end
  M.declared_names_cache = normalized
end

-- Per-plugin declared version intent published by `core.plugins.setup`:
--   name -> { resolved = nil|string|vim.VersionRange, star = boolean }
-- Used to flag spec-vs-disk drift and risky `version = "*"` pins. Empty until
-- set (so pre-setup dashboard access doesn't mis-classify rows).
function M.set_declared_plugin_versions(versions)
  if type(versions) ~= "table" then
    M.declared_versions_cache = {}
    M.version_flags_cache = {}
    M.version_flags_scanned = false
    return
  end
  M.declared_versions_cache = versions
  M.version_flags_cache = {}
  M.version_flags_scanned = false
end

local function normalize_epoch(value)
  if type(value) ~= "number" then
    return nil
  end
  if value <= 0 then
    return nil
  end
  return math.floor(value)
end

function M.normalize_epoch(value)
  return normalize_epoch(value)
end

function M.format_cache_stamp(epoch)
  epoch = normalize_epoch(epoch)
  if not epoch then
    return "never"
  end

  local now = os.time()
  if os.date("%Y-%m-%d", epoch) == os.date("%Y-%m-%d", now) then
    return os.date("%H:%M:%S", epoch)
  end
  return os.date("%Y-%m-%d %H:%M", epoch)
end

function M.normalize_mode(value, allowed, fallback)
  if type(value) ~= "string" then
    return fallback
  end
  return allowed[value] and value or fallback
end

function M.normalize_selected_names(value)
  if type(value) ~= "table" then
    return {}
  end
  local out = {}
  local seen = {}
  for _, name in ipairs(value) do
    if type(name) == "string" and name ~= "" and not seen[name] then
      seen[name] = true
      out[#out + 1] = name
    end
  end
  table.sort(out)
  return out
end

function M.write_persisted_state()
  local cache = M.pack_report_cache
  local ui = M.dashboard_ui_cache
  local payload = {
    updated_at = normalize_epoch(cache.updated_at),
    mode = cache.mode,
    last_online_at = normalize_epoch(cache.last_online_at),
    last_offline_at = normalize_epoch(cache.last_offline_at),
    last_applied_at = normalize_epoch(cache.last_applied_at),
    last_applied_count = tonumber(cache.last_applied_count) or 0,
    last_check_counts = cache.last_check_counts,
    plugins = cache.plugins,
    ui = {
      filter_mode = ui.filter_mode,
      sort_mode = ui.sort_mode,
      search_text = ui.search_text,
      selected_names = ui.selected_names,
    },
  }
  local ok_json, encoded = pcall(vim.json.encode, payload)
  if not ok_json or type(encoded) ~= "string" or encoded == "" then
    return
  end
  pcall(vim.fn.writefile, { encoded }, persisted_state_path())
end

function M.load_persisted_state_once()
  if M.persisted_state_loaded then
    return
  end
  M.persisted_state_loaded = true

  local path = persisted_state_path()
  if vim.fn.filereadable(path) ~= 1 then
    return
  end

  local ok_read, file_lines = pcall(vim.fn.readfile, path)
  if not ok_read or type(file_lines) ~= "table" or #file_lines == 0 then
    return
  end

  local ok_decode, decoded = pcall(vim.json.decode, table.concat(file_lines, "\n"))
  if not ok_decode or type(decoded) ~= "table" then
    return
  end

  local cache = M.pack_report_cache
  cache.updated_at = normalize_epoch(decoded.updated_at)
  cache.last_online_at = normalize_epoch(decoded.last_online_at)
  cache.last_offline_at = normalize_epoch(decoded.last_offline_at)
  cache.last_applied_at = normalize_epoch(decoded.last_applied_at)
  cache.last_applied_count = tonumber(decoded.last_applied_count) or 0
  if type(decoded.plugins) == "table" then
    local restored = {}
    for name, info in pairs(decoded.plugins) do
      if type(name) == "string" and type(info) == "table" then
        restored[name] = info
      end
    end
    cache.plugins = restored
  end
  if type(decoded.last_check_counts) == "table" then
    cache.last_check_counts = {
      update = tonumber(decoded.last_check_counts.update) or 0,
      same = tonumber(decoded.last_check_counts.same) or 0,
      error = tonumber(decoded.last_check_counts.error) or 0,
    }
  end

  if decoded.mode == "online" or decoded.mode == "offline" or decoded.mode == "unknown" then
    cache.mode = decoded.mode
  end

  if type(decoded.ui) == "table" then
    local ui = M.dashboard_ui_cache
    ui.filter_mode =
      M.normalize_mode(decoded.ui.filter_mode, { all = true, updates = true, issues = true, selected = true }, "all")
    ui.sort_mode = M.normalize_mode(decoded.ui.sort_mode, { status = true, name = true }, "status")
    if type(decoded.ui.search_text) == "string" and decoded.ui.search_text ~= "" then
      ui.search_text = decoded.ui.search_text
    else
      ui.search_text = nil
    end
    ui.selected_names = M.normalize_selected_names(decoded.ui.selected_names)
  end
end

return M
