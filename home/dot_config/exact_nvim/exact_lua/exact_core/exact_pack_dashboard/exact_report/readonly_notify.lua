local state = require("core.pack_dashboard.state")

local M = {}

local function notify_err(msg)
  vim.schedule(function()
    vim.notify(msg, vim.log.levels.ERROR)
  end)
end

local function format_check_counts(counts)
  if type(counts) ~= "table" then
    return "update:n/a same:n/a error:n/a"
  end

  return string.format(
    "update:%d same:%d error:%d",
    tonumber(counts.update) or 0,
    tonumber(counts.same) or 0,
    tonumber(counts.error) or 0
  )
end

local function pending_update_names(limit)
  local plugins = state.pack_report_cache.plugins
  if type(plugins) ~= "table" then
    return nil
  end

  local names = {}
  for name, data in pairs(plugins) do
    if type(name) == "string" and type(data) == "table" and data.status == "update" then
      names[#names + 1] = name
    end
  end

  if #names == 0 then
    return nil
  end

  table.sort(names)
  limit = math.max(1, tonumber(limit) or 5)
  local shown = {}
  for i = 1, math.min(#names, limit) do
    shown[#shown + 1] = names[i]
  end

  local suffix = #names > limit and string.format(", +%d more", #names - limit) or ""
  return table.concat(shown, ", ") .. suffix
end

local function notify_check_start(online)
  local msg = online and "Checking plugin updates online..." or "Computing local plugin status (offline; no fetch)..."
  vim.notify(msg, vim.log.levels.INFO)
end

local function notify_check_result(online, counts)
  local label = online and "Online plugin check" or "Offline plugin status"
  local msg = label .. ": " .. format_check_counts(counts)
  local names = online and pending_update_names(5) or nil
  if names then
    msg = msg .. " (" .. names .. ")"
  elseif not online then
    msg = msg .. " (no remotes fetched)"
  end
  vim.notify(msg, vim.log.levels.INFO)
end

M.notify_err = notify_err
M.notify_check_start = notify_check_start
M.notify_check_result = notify_check_result

return M
