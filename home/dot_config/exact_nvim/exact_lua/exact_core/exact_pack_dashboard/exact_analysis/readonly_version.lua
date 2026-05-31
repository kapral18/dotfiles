local state = require("core.pack_dashboard.state")
local gitcmd = require("core.pack_dashboard.analysis.gitcmd")

local M = {}

local function is_commit_string(s)
  return type(s) == "string" and s:match("^%x%x%x%x%x%x%x+$") ~= nil and #s >= 7
end

local function is_version_range(v)
  return type(v) == "table" and type(v.has) == "function"
end

-- A release-shaped tag: optional leading `v`, then numeric `X.Y[.Z]`. Excludes
-- junk like `nvim-0.6`, `0.1.x`, `nightly` that poison `version = "*"`.
local function is_release_tag(t)
  if type(t) ~= "string" then
    return false
  end
  local body = t:gsub("^v", "")
  return body:match("^%d+%.%d+%.%d+$") ~= nil or body:match("^%d+%.%d+$") ~= nil
end

local function greatest_tag(tags, filter)
  local best
  for _, t in ipairs(tags or {}) do
    if (not filter) or filter(t) then
      local v = vim.version.parse(t)
      if v and (not best or vim.version.gt(v, best.v)) then
        best = { t = t, v = v }
      end
    end
  end
  return best and best.t or nil
end

-- True when the on-disk checkout no longer satisfies the declared version.
-- `declared` is the resolved spec version; `plugin` is a `vim.pack.get` entry
-- (with `rev` and `tags` = tags pointing at the current rev).
local function compute_version_drift(declared, plugin)
  if declared == nil then
    -- Branch-tracking / `version = false`: no constraint provable offline.
    return false
  end
  local rev = plugin.rev or ""
  local tags = plugin.tags or {}

  if is_version_range(declared) then
    for _, t in ipairs(tags) do
      local v = vim.version.parse(t)
      if v and declared:has(v) then
        return false
      end
    end
    return true
  end

  if is_commit_string(declared) then
    return not (rev == declared or rev:sub(1, #declared) == declared)
  end

  -- Plain branch or tag string.
  for _, t in ipairs(tags) do
    if t == declared then
      return false
    end
  end
  -- Looks like a tag (has a digit) and is absent: drift. A pure branch name
  -- can't be confirmed offline, so don't flag it.
  return declared:match("%d") ~= nil
end

-- True when `version = "*"` would select a non-release tag that outranks the
-- greatest real release tag (the telescope `nvim-0.6` > `v0.2.2` footgun).
local function detect_risky_star_pin(is_star, tags)
  if not is_star or type(tags) ~= "table" or #tags == 0 then
    return false
  end
  local star_pick = greatest_tag(tags, nil)
  local intended = greatest_tag(tags, is_release_tag)
  if not intended then
    return false
  end
  return star_pick ~= intended
end

local function needs_current_revision_tags(resolved)
  return is_version_range(resolved)
    or (type(resolved) == "string" and not is_commit_string(resolved) and resolved:match("%d") ~= nil)
end

local function refresh_version_flags_async(done)
  if state.version_flags_scan_running or state.version_flags_scanned or next(state.declared_versions_cache) == nil then
    return
  end

  local ok, plugins = pcall(vim.pack.get, nil, { info = false })
  if not ok or type(plugins) ~= "table" then
    return
  end

  state.version_flags_scan_running = true
  local index = 1
  local function step()
    -- Process a few rows per tick so slow git tag calls never delay opening the
    -- dashboard. Rows use the cached result on the next render.
    local processed = 0
    while index <= #plugins and processed < 4 do
      local plugin = plugins[index]
      index = index + 1
      processed = processed + 1

      local name = plugin.spec and plugin.spec.name
      local intent = type(name) == "string" and state.declared_versions_cache[name] or nil
      local is_orphan = next(state.declared_names_cache) ~= nil and not state.declared_names_cache[name]
      if type(intent) == "table" and not is_orphan then
        local plugin_for_drift = plugin
        if needs_current_revision_tags(intent.resolved) then
          plugin_for_drift =
            vim.tbl_extend("force", plugin, { tags = gitcmd.tags_on_revision(plugin.path, plugin.rev) })
        end

        state.version_flags_cache[name] = {
          drift = compute_version_drift(intent.resolved, plugin_for_drift) or nil,
          risky = detect_risky_star_pin(intent.star, intent.star and gitcmd.all_tags(plugin.path) or nil) or nil,
        }
      end
    end

    if index <= #plugins then
      vim.defer_fn(step, 0)
      return
    end

    state.version_flags_scan_running = false
    state.version_flags_scanned = true
    if type(done) == "function" then
      done()
    end
  end

  vim.defer_fn(step, 0)
end

local function short_rev(rev)
  if type(rev) ~= "string" or rev == "" then
    return nil
  end
  return rev:sub(1, 8)
end

M.is_commit_string = is_commit_string
M.is_version_range = is_version_range
M.is_release_tag = is_release_tag
M.compute_version_drift = compute_version_drift
M.detect_risky_star_pin = detect_risky_star_pin
M.refresh_version_flags_async = refresh_version_flags_async
M.short_rev = short_rev

return M
