local state = require("core.pack_dashboard.state")
local analysis = require("core.pack_dashboard.analysis")

local M = {}

local function parse_pack_report_buffer(bufnr, merge)
  if not bufnr or not vim.api.nvim_buf_is_valid(bufnr) then
    return
  end

  local lines = vim.api.nvim_buf_get_lines(bufnr, 0, -1, false)
  if #lines == 0 then
    return
  end

  local current_group = nil
  local current_plugin = nil
  local plugins = {}
  local counts = { update = 0, same = 0, error = 0 }

  for _, line in ipairs(lines) do
    local section = line:match("^#%s+(%u%l+)")
    if section then
      local normalized = section:lower()
      if normalized == "update" or normalized == "same" or normalized == "error" then
        current_group = normalized
      else
        current_group = nil
      end
      current_plugin = nil
    elseif current_group then
      local name = line:match("^##%s+(.+)$")
      if name then
        name = vim.trim(name:gsub("%s*%(.+%)$", ""))
        current_plugin = {
          status = current_group,
          pending_lines = {},
        }
        plugins[name] = current_plugin
        if counts[current_group] ~= nil then
          counts[current_group] = counts[current_group] + 1
        end
      elseif current_plugin then
        local path = line:match("^Path:%s+(.+)$")
        if path then
          current_plugin.path = vim.trim(path)
        end

        local source = line:match("^Source:%s+(.+)$")
        if source then
          current_plugin.source = vim.trim(source)
        end

        local rev_before = line:match("^Revision before:%s+([0-9a-fA-F]+)")
        if rev_before then
          current_plugin.rev_before = rev_before
        end

        local rev_after_line = line:match("^Revision after:%s+(.+)$")
        if rev_after_line then
          current_plugin.rev_after = rev_after_line:match("^([0-9a-fA-F]+)") or current_plugin.rev_after
          current_plugin.target_version = rev_after_line:match("%(([^)]+)%)")
        end

        local rev_line = line:match("^Revision:%s+(.+)$")
        if rev_line then
          current_plugin.rev = rev_line:match("^([0-9a-fA-F]+)") or current_plugin.rev
          current_plugin.current_version = rev_line:match("%(([^)]+)%)")
        end

        if line:match("^Pending updates:%s*$") then
          current_plugin.collect_pending = true
        elseif current_plugin.collect_pending then
          if
            line:match("^#%s+")
            or line:match("^##%s+")
            or line:match("^Path:%s+")
            or line:match("^Source:%s+")
            or line:match("^Revision%s+")
          then
            current_plugin.collect_pending = false
          elseif line ~= "" then
            current_plugin.pending_lines[#current_plugin.pending_lines + 1] = line
          end
        end
      end
    end
  end

  for _, p_data in pairs(plugins) do
    p_data.pending_updates = table.concat(p_data.pending_lines or {}, "\n")
    p_data.breaking = analysis.infer_breaking_status(p_data)
    p_data.diff_url = analysis.source_to_compare_url(p_data.source, p_data.rev_before, p_data.rev_after)
    p_data.pending_lines = nil
    p_data.collect_pending = nil
  end

  if merge then
    local merged = vim.deepcopy(state.pack_report_cache.plugins or {})
    for name, data in pairs(plugins) do
      merged[name] = data
    end
    state.pack_report_cache.plugins = merged
  else
    state.pack_report_cache.plugins = plugins
  end
  state.pack_report_cache.updated_at = os.time()
  state.write_persisted_state()
  return counts
end

local function find_pack_report_buffer()
  local current = vim.api.nvim_get_current_buf()
  local current_name = vim.api.nvim_buf_get_name(current)
  if current_name:match("^nvim%-pack://confirm#") then
    return current
  end

  local matched = nil
  for _, bufnr in ipairs(vim.api.nvim_list_bufs()) do
    if vim.api.nvim_buf_is_valid(bufnr) then
      local name = vim.api.nvim_buf_get_name(bufnr)
      if name:match("^nvim%-pack://confirm#") then
        matched = bufnr
      end
    end
  end

  return matched
end

local function refresh_pack_report_cache_from_report_buffer(merge)
  local bufnr = find_pack_report_buffer()
  if bufnr then
    return parse_pack_report_buffer(bufnr, merge), bufnr
  end
  return nil, nil
end

M.parse_pack_report_buffer = parse_pack_report_buffer
M.find_pack_report_buffer = find_pack_report_buffer
M.refresh_pack_report_cache_from_report_buffer = refresh_pack_report_cache_from_report_buffer

return M
