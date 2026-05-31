local state = require("core.pack_dashboard.state")
local report = require("core.pack_dashboard.report")
local ui = require("core.pack_dashboard.ui")
local lockfile = require("core.pack_dashboard.lockfile")
local policy = require("core.pack.policy")

local M = {}

local configured = false
local load_version_policy = policy.load_version_policy
local rebuild_version_policy = policy.rebuild_version_policy
local refresh_version_policy_if_needed = policy.refresh_version_policy_if_needed

function M.set_declared_plugin_names(names)
  state.set_declared_plugin_names(names)
end

function M.set_declared_plugin_versions(versions)
  state.set_declared_plugin_versions(versions)
end

function M.lockfile_path()
  return lockfile.path()
end

function M.export_lockfile(destination)
  return lockfile.export(destination)
end

function M.import_lockfile(source)
  return lockfile.import(source)
end

function M.setup()
  if configured then
    return
  end
  configured = true
  state.load_persisted_state_once()

  vim.api.nvim_create_user_command("PackSync", function()
    vim.pack.update()
    local counts = report.refresh_pack_report_cache_from_report_buffer()
    if counts then
      state.pack_report_cache.last_check_counts = counts
    end
    state.pack_report_cache.mode = "online"
    state.pack_report_cache.last_online_at = os.time()
    state.write_persisted_state()
    pcall(refresh_version_policy_if_needed)
  end, {
    desc = "Check updates online (fetch remotes)",
  })

  vim.api.nvim_create_user_command("PackStatus", function()
    vim.pack.update(nil, { offline = true })
    local counts = report.refresh_pack_report_cache_from_report_buffer()
    if counts then
      state.pack_report_cache.last_check_counts = counts
    end
    state.pack_report_cache.mode = "offline"
    state.pack_report_cache.last_offline_at = os.time()
    state.write_persisted_state()
    pcall(refresh_version_policy_if_needed)
  end, {
    desc = "Show status from local refs only (offline)",
  })

  vim.api.nvim_create_user_command("PackDashboardStats", function()
    local raw = state.pack_report_cache.last_check_counts
    local raw_text = "update:n/a same:n/a error:n/a"
    if type(raw) == "table" then
      raw_text = string.format(
        "update:%d same:%d error:%d",
        tonumber(raw.update) or 0,
        tonumber(raw.same) or 0,
        tonumber(raw.error) or 0
      )
    end
    local checked = state.format_cache_stamp(state.pack_report_cache.updated_at)
    local online = state.format_cache_stamp(state.pack_report_cache.last_online_at)
    local offline = state.format_cache_stamp(state.pack_report_cache.last_offline_at)
    local applied = state.format_cache_stamp(state.pack_report_cache.last_applied_at)
    local applied_count = tonumber(state.pack_report_cache.last_applied_count) or 0
    vim.notify(
      string.format(
        "PackDashboard last-check [%s] mode:%s result:%s online:%s offline:%s applied:%s (%d)",
        raw_text,
        state.pack_report_cache.mode or "unknown",
        checked,
        online,
        offline,
        applied,
        applied_count
      ),
      vim.log.levels.INFO
    )
  end, {
    desc = "Show last raw vim.pack check counters",
  })

  vim.api.nvim_create_user_command("PackDashboard", function(cmd)
    ui.open(true, cmd.bang)
  end, {
    bang = true,
    desc = "Open vim.pack dashboard with update risk and diff links",
  })

  vim.api.nvim_create_user_command("PackMenu", function(cmd)
    ui.open(true, cmd.bang)
  end, {
    bang = true,
    desc = "Open vim.pack dashboard (legacy alias)",
  })

  vim.api.nvim_create_user_command("PackLockInfo", function()
    local path = lockfile.path()
    if vim.fn.filereadable(path) ~= 1 then
      vim.notify("vim.pack lockfile not found at " .. path, vim.log.levels.WARN)
      return
    end
    local ok_read, lines = pcall(vim.fn.readfile, path)
    local plugins = 0
    if ok_read and type(lines) == "table" then
      local ok_decode, decoded = pcall(vim.json.decode, table.concat(lines, "\n"))
      if ok_decode and type(decoded) == "table" and type(decoded.plugins) == "table" then
        for _ in pairs(decoded.plugins) do
          plugins = plugins + 1
        end
      end
    end
    local stat = vim.uv.fs_stat(path)
    local mtime = stat and os.date("%Y-%m-%d %H:%M:%S", stat.mtime.sec) or "unknown"
    vim.notify(
      string.format("vim.pack lockfile: %s\n  plugins: %d\n  mtime:   %s", path, plugins, mtime),
      vim.log.levels.INFO
    )
  end, {
    desc = "Show vim.pack lockfile path, plugin count, mtime",
  })

  vim.api.nvim_create_user_command("PackLockExport", function(cmd)
    local dest = cmd.args
    if type(dest) ~= "string" or dest == "" then
      vim.notify("Usage: :PackLockExport <path>", vim.log.levels.WARN)
      return
    end
    local ok, result = lockfile.export(dest)
    if ok then
      vim.notify("Exported lockfile → " .. result, vim.log.levels.INFO)
    else
      vim.notify("PackLockExport failed: " .. tostring(result), vim.log.levels.ERROR)
    end
  end, {
    nargs = 1,
    complete = "file",
    desc = "Copy nvim-pack-lock.json to an arbitrary path (for dotfile sync)",
  })

  vim.api.nvim_create_user_command("PackPolicyRebuild", function(cmd)
    local arg = vim.trim(cmd.args or "")
    local target = arg ~= "" and arg or nil
    local ok = rebuild_version_policy(target)
    if ok then
      local version_policy = load_version_policy() or { plugins = {} }
      if target then
        local info = version_policy.plugins and version_policy.plugins[target]
        if info then
          vim.notify(
            string.format(
              "Rebuilt policy for %s: strategy=%s\n  %s",
              target,
              tostring(info.strategy),
              tostring(info.reason or "")
            ),
            vim.log.levels.INFO
          )
        else
          vim.notify("Rebuilt policy, but no entry recorded for " .. target, vim.log.levels.WARN)
        end
      else
        local count = 0
        local tags, branch = 0, 0
        for _, info in pairs(version_policy.plugins or {}) do
          count = count + 1
          if info.strategy == "tags" then
            tags = tags + 1
          elseif info.strategy == "branch" then
            branch = branch + 1
          end
        end
        vim.notify(
          string.format("Rebuilt version policy: %d plugins (%d tags, %d branch)", count, tags, branch),
          vim.log.levels.INFO
        )
      end
    else
      vim.notify("PackPolicyRebuild failed", vim.log.levels.ERROR)
    end
  end, {
    nargs = "?",
    complete = function(arglead)
      local ok, plug_data = pcall(vim.pack.get, nil, { info = false })
      if not ok or type(plug_data) ~= "table" then
        return {}
      end
      local out = {}
      for _, p in ipairs(plug_data) do
        local n = p and p.spec and p.spec.name
        if type(n) == "string" and (arglead == "" or n:find(arglead, 1, true)) then
          out[#out + 1] = n
        end
      end
      table.sort(out)
      return out
    end,
    desc = "Clear and recompute the cached per-plugin tag/branch heuristic. Pass plugin name for a targeted rebuild.",
  })

  vim.api.nvim_create_user_command("PackLockImport", function(cmd)
    local source = cmd.args
    if type(source) ~= "string" or source == "" then
      vim.notify("Usage: :PackLockImport <path>", vim.log.levels.WARN)
      return
    end
    local ok, result = lockfile.import(source)
    if ok then
      vim.notify(
        "Imported lockfile from " .. source .. " → " .. result .. ". Restart or run :PackSync to apply.",
        vim.log.levels.INFO
      )
    else
      vim.notify("PackLockImport failed: " .. tostring(result), vim.log.levels.ERROR)
    end
  end, {
    nargs = 1,
    complete = "file",
    desc = "Overwrite nvim-pack-lock.json from a path (for dotfile sync)",
  })
end

return M
