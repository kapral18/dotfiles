local M = {}

local configured = false
local pack_report_cache = { plugins = {}, updated_at = nil, mode = nil }
local dashboard_ns = vim.api.nvim_create_namespace("core.pack_dashboard")

local function ensure_dashboard_highlights()
  local set_hl = vim.api.nvim_set_hl
  set_hl(0, "PackDashboardTitle", { default = true, link = "Title" })
  set_hl(0, "PackDashboardStats", { default = true, link = "Special" })
  set_hl(0, "PackDashboardMeta", { default = true, link = "Comment" })
  set_hl(0, "PackDashboardHeader", { default = true, link = "Identifier" })
  set_hl(0, "PackDashboardStatusUpdate", { default = true, link = "DiagnosticInfo" })
  set_hl(0, "PackDashboardStatusSame", { default = true, link = "String" })
  set_hl(0, "PackDashboardStatusError", { default = true, link = "DiagnosticError" })
  set_hl(0, "PackDashboardStatusUnknown", { default = true, link = "Comment" })
  set_hl(0, "PackDashboardRiskBreak", { default = true, link = "DiagnosticWarn" })
  set_hl(0, "PackDashboardRiskSafe", { default = true, link = "DiffAdd" })
  set_hl(0, "PackDashboardRiskUnknown", { default = true, link = "Comment" })
  set_hl(0, "PackDashboardLink", { default = true, link = "Underlined" })
  set_hl(0, "PackDashboardSelected", { default = true, link = "IncSearch" })
end

local function notify_err(msg)
  vim.schedule(function()
    vim.notify(msg, vim.log.levels.ERROR)
  end)
end

local function semver_major(version)
  if type(version) ~= "string" or version == "" then
    return nil
  end
  local major = version:match("^v?(%d+)%.") or version:match("^v?(%d+)$")
  return major and tonumber(major) or nil
end

local revision_tag_cache = {}
local function tag_on_revision(path, rev)
  if type(path) ~= "string" or path == "" or type(rev) ~= "string" or rev == "" then
    return nil
  end
  local key = path .. "@" .. rev
  if revision_tag_cache[key] ~= nil then
    return revision_tag_cache[key]
  end

  local result = vim.system({ "git", "-C", path, "tag", "--points-at", rev }, { text = true }):wait()
  if result.code ~= 0 or type(result.stdout) ~= "string" then
    revision_tag_cache[key] = false
    return nil
  end

  local tags = {}
  for _, line in ipairs(vim.split(result.stdout, "\n", { trimempty = true })) do
    if line ~= "" then
      tags[#tags + 1] = line
    end
  end

  table.sort(tags, function(a, b)
    local ma, mb = semver_major(a) or -1, semver_major(b) or -1
    if ma ~= mb then
      return ma > mb
    end
    return a > b
  end)

  revision_tag_cache[key] = tags[1] or false
  return revision_tag_cache[key] or nil
end

local function parse_source_coordinates(src)
  if type(src) ~= "string" or src == "" then
    return nil
  end

  local normalized = vim.trim(src):gsub("/+$", "")
  local host, owner, repo = normalized:match("^https?://([^/]+)/([^/]+)/([^/]+)%.git$")
  if not host then
    host, owner, repo = normalized:match("^https?://([^/]+)/([^/]+)/([^/]+)$")
  end
  if not host then
    host, owner, repo = normalized:match("^git@([^:]+):([^/]+)/([^/]+)%.git$")
  end
  if not host then
    host, owner, repo = normalized:match("^git@([^:]+):([^/]+)/([^/]+)$")
  end
  if not host then
    host, owner, repo = normalized:match("^ssh://git@([^/]+)/([^/]+)/([^/]+)%.git$")
  end
  if not host then
    host, owner, repo = normalized:match("^ssh://git@([^/]+)/([^/]+)/([^/]+)$")
  end
  if not host or not owner or not repo then
    return nil
  end

  repo = repo:gsub("%.git$", "")
  return host, owner, repo
end

local function source_to_compare_url(src, rev_before, rev_after)
  if type(src) ~= "string" or src == "" or type(rev_before) ~= "string" or type(rev_after) ~= "string" then
    return nil
  end

  local host, owner, repo = parse_source_coordinates(src)
  if not host or not owner or not repo then
    return nil
  end

  if host == "github.com" or host == "codeberg.org" then
    return ("https://%s/%s/%s/compare/%s...%s"):format(host, owner, repo, rev_before, rev_after)
  end
  return nil
end

local function source_to_repo_url(src)
  if type(src) ~= "string" or src == "" then
    return nil
  end

  local host, owner, repo = parse_source_coordinates(src)
  if not host or not owner or not repo then
    return nil
  end
  return ("https://%s/%s/%s"):format(host, owner, repo)
end

local function repo_to_compare_url(repo_url, from_ref, to_ref)
  if type(repo_url) ~= "string" or repo_url == "" then
    return nil
  end
  if type(from_ref) ~= "string" or from_ref == "" or type(to_ref) ~= "string" or to_ref == "" then
    return nil
  end

  local host, owner, repo = repo_url:match("^https://([^/]+)/([^/]+)/([^/]+)$")
  if not host or not owner or not repo then
    return nil
  end
  if host == "github.com" or host == "codeberg.org" then
    return ("%s/compare/%s...%s"):format(repo_url, from_ref, to_ref)
  end
  return nil
end

local function short_rev(rev)
  if type(rev) ~= "string" or rev == "" then
    return nil
  end
  return rev:sub(1, 8)
end

local function infer_breaking_status(p_data)
  if p_data.status ~= "update" then
    return nil
  end

  local details = (p_data.pending_updates or ""):lower()
  if details:find("breaking change", 1, true) or details:find("breaking", 1, true) then
    return true
  end

  local before_version = p_data.current_version or tag_on_revision(p_data.path, p_data.rev_before)
  local after_version = p_data.target_version or tag_on_revision(p_data.path, p_data.rev_after)
  p_data.current_version = before_version
  p_data.target_version = after_version

  local before_major = semver_major(before_version)
  local after_major = semver_major(after_version)
  if before_major and after_major then
    return after_major > before_major
  end
  return nil
end

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
    p_data.breaking = infer_breaking_status(p_data)
    p_data.diff_url = source_to_compare_url(p_data.source, p_data.rev_before, p_data.rev_after)
    p_data.pending_lines = nil
    p_data.collect_pending = nil
  end

  if merge then
    local merged = vim.deepcopy(pack_report_cache.plugins or {})
    for name, data in pairs(plugins) do
      merged[name] = data
    end
    pack_report_cache.plugins = merged
  else
    pack_report_cache.plugins = plugins
  end
  pack_report_cache.updated_at = os.time()
end

local function refresh_pack_report_cache_from_current_buffer(merge)
  local bufnr = vim.api.nvim_get_current_buf()
  local name = vim.api.nvim_buf_get_name(bufnr)
  if name:match("^nvim%-pack://confirm#") then
    parse_pack_report_buffer(bufnr, merge)
    return true
  end
  return false
end

local function scan_updates_to_cache(online, names, merge)
  vim.pack.update(names, online and nil or { offline = true })
  if not refresh_pack_report_cache_from_current_buffer(merge) then
    notify_err("Failed to capture vim.pack report buffer")
    return false
  end
  pack_report_cache.mode = online and "online" or "offline"
  pcall(vim.cmd.quit)
  return true
end

local function ensure_dashboard_cache(online, force_scan)
  if force_scan then
    return scan_updates_to_cache(online, nil, false)
  end
  if type(pack_report_cache.plugins) == "table" and next(pack_report_cache.plugins) ~= nil then
    return true
  end
  return scan_updates_to_cache(online, nil, false)
end

local function collect_dashboard_rows()
  local ok, plugins = pcall(vim.pack.get, nil, { info = false })
  if not ok then
    notify_err("Failed to read vim.pack plugins")
    return {}
  end

  local rows = {}
  for _, plugin in ipairs(plugins) do
    local name = plugin.spec.name
    local p_data = pack_report_cache.plugins[name] or {}
    local status = p_data.status or "unknown"
    local source = p_data.source or plugin.spec.src
    local diff_url = p_data.diff_url or source_to_compare_url(source, p_data.rev_before, p_data.rev_after)
    local breaking = p_data.breaking
    if breaking == nil and status == "update" then
      p_data.source = source
      p_data.diff_url = diff_url
      p_data.breaking = infer_breaking_status(p_data)
      breaking = p_data.breaking
    end

    rows[#rows + 1] = {
      name = name,
      status = status,
      source = source,
      target_version = p_data.target_version,
      current_version = p_data.current_version,
      rev_before = p_data.rev_before,
      rev_after = p_data.rev_after,
      pending_updates = p_data.pending_updates,
      breaking = breaking,
      diff_url = diff_url,
      repo_url = source_to_repo_url(source),
    }
  end

  for _, row in ipairs(rows) do
    if not row.diff_url and row.status == "update" and row.repo_url then
      local from_ref = row.current_version or row.rev_before
      local to_ref = row.target_version or row.rev_after
      row.diff_url = repo_to_compare_url(row.repo_url, from_ref, to_ref)
    end
  end

  return rows
end

local function open_pack_dashboard(online, force_scan)
  if not ensure_dashboard_cache(online, force_scan) then
    return
  end

  local use_nerd_font = vim.g.pack_dashboard_ascii ~= true
  local fast_scroll_mode = vim.g.pack_dashboard_fast_scroll ~= false
  local icons = use_nerd_font
      and {
        update = "",
        same = "",
        error = "",
        unknown = "",
        risk_break = "",
        risk_safe = "",
        risk_unknown = "",
        link_diff = "",
        link_repo = "",
      }
    or {
      update = "U",
      same = "=",
      error = "!",
      unknown = "?",
      risk_break = "!",
      risk_safe = "+",
      risk_unknown = "?",
      link_diff = "diff",
      link_repo = "repo",
    }
  local status_icon = {
    update = icons.update,
    same = icons.same,
    error = icons.error,
    unknown = icons.unknown,
  }
  local status_rank = { update = 1, error = 2, same = 3, unknown = 4 }
  local filter_modes = { "all", "updates", "issues", "selected" }
  local rows = collect_dashboard_rows()
  local selected = {}
  local row_by_line = {}
  local first_data_line = 1
  local filter_mode = "all"
  local sort_mode = "status"
  local search_text = nil
  local winid
  local details_winid
  local details_bufnr

  local bufnr = vim.api.nvim_create_buf(false, true)
  vim.bo[bufnr].buftype = "nofile"
  vim.bo[bufnr].bufhidden = "wipe"
  vim.bo[bufnr].buflisted = false
  vim.bo[bufnr].swapfile = false
  vim.bo[bufnr].modifiable = true
  vim.bo[bufnr].filetype = "packdashboard"

  local function open_popup_window()
    local total_lines = vim.o.lines - vim.o.cmdheight
    local width_ratio = tonumber(vim.g.pack_dashboard_width_ratio) or 0.68
    local height_ratio = tonumber(vim.g.pack_dashboard_height_ratio) or 0.68
    local min_width = tonumber(vim.g.pack_dashboard_min_width) or 84
    local min_height = tonumber(vim.g.pack_dashboard_min_height) or 18
    local margin = tonumber(vim.g.pack_dashboard_margin) or 6

    width_ratio = math.max(0.45, math.min(0.98, width_ratio))
    height_ratio = math.max(0.45, math.min(0.98, height_ratio))
    margin = math.max(2, margin)

    local width = math.min(math.max(min_width, math.floor(vim.o.columns * width_ratio)), vim.o.columns - margin)
    local height = math.min(math.max(min_height, math.floor(total_lines * height_ratio)), total_lines - margin)
    local row = math.floor((total_lines - height) / 2)
    local col = math.floor((vim.o.columns - width) / 2)

    winid = vim.api.nvim_open_win(bufnr, true, {
      relative = "editor",
      style = "minimal",
      border = "rounded",
      title = " vim.pack dashboard ",
      title_pos = "center",
      row = row,
      col = col,
      width = width,
      height = height,
    })

    vim.wo[winid].number = false
    vim.wo[winid].relativenumber = false
    vim.wo[winid].signcolumn = "no"
    vim.wo[winid].foldcolumn = "0"
    vim.wo[winid].wrap = false
    vim.wo[winid].cursorline = false
    vim.wo[winid].smoothscroll = false
  end

  local function close_details_popup()
    if details_winid and vim.api.nvim_win_is_valid(details_winid) then
      pcall(vim.api.nvim_win_close, details_winid, true)
    end
    if details_bufnr and vim.api.nvim_buf_is_valid(details_bufnr) then
      pcall(vim.api.nvim_buf_delete, details_bufnr, { force = true })
    end
    details_winid = nil
    details_bufnr = nil
  end

  local function risk_label(row)
    if row.status ~= "update" then
      return "-"
    end
    if row.breaking == true then
      return icons.risk_break
    end
    if row.breaking == false then
      return icons.risk_safe
    end
    return icons.risk_unknown
  end

  local function links_cell(row)
    local has_diff = row.diff_url ~= nil
    local has_repo = row.repo_url ~= nil

    -- Compact availability indicators: prefer diff, then repo fallback.
    if has_diff then
      return icons.link_diff
    end
    if has_repo then
      return icons.link_repo
    end
    return "-"
  end

  local function truncate_cell(text, max_width)
    if type(text) ~= "string" then
      text = tostring(text or "")
    end
    if max_width <= 1 then
      return text:sub(1, max_width)
    end
    if #text <= max_width then
      return text
    end
    return text:sub(1, max_width - 1) .. "…"
  end

  local function cycle_filter_mode()
    for i, mode in ipairs(filter_modes) do
      if mode == filter_mode then
        filter_mode = filter_modes[(i % #filter_modes) + 1]
        return
      end
    end
    filter_mode = filter_modes[1]
  end

  local function visible_rows()
    local out = {}
    for _, row in ipairs(rows) do
      local include = true
      if filter_mode == "updates" then
        include = row.status == "update"
      elseif filter_mode == "issues" then
        include = row.status == "update" or row.status == "error"
      elseif filter_mode == "selected" then
        include = selected[row.name] == true
      end

      if include and search_text and search_text ~= "" then
        include = row.name:lower():find(search_text:lower(), 1, true) ~= nil
      end

      if include then
        out[#out + 1] = row
      end
    end

    if sort_mode == "name" then
      table.sort(out, function(a, b)
        return a.name < b.name
      end)
    else
      table.sort(out, function(a, b)
        local ra = status_rank[a.status] or status_rank.unknown
        local rb = status_rank[b.status] or status_rank.unknown
        if ra ~= rb then
          return ra < rb
        end
        return a.name < b.name
      end)
    end

    return out
  end

  local function summary_counts()
    local counts = { update = 0, same = 0, error = 0, unknown = 0, breaking = 0 }
    for _, row in ipairs(rows) do
      counts[row.status] = (counts[row.status] or 0) + 1
      if row.breaking == true then
        counts.breaking = counts.breaking + 1
      end
    end
    return counts
  end

  local function selected_count(visible_only)
    local count = 0
    local scope = visible_only and visible_rows() or rows
    for _, row in ipairs(scope) do
      if selected[row.name] then
        count = count + 1
      end
    end
    return count
  end

  local function selected_names(visible_only)
    local names = {}
    local scope = visible_only and visible_rows() or rows
    for _, row in ipairs(scope) do
      if selected[row.name] then
        names[#names + 1] = row.name
      end
    end
    return names
  end

  local function version_cell(row)
    local current = row.current_version or short_rev(row.rev_before) or short_rev(row.rev)
    local target = row.target_version or short_rev(row.rev_after)
    if row.status == "update" then
      current = current or "-"
      target = target or "-"
      return current .. " -> " .. target
    end
    return current or "-"
  end

  local function open_details_popup(row)
    if not row then
      return
    end
    close_details_popup()

    local pending = row.pending_updates
    if type(pending) ~= "string" or pending == "" then
      pending = "(No pending update details available)"
    end

    local lines = {
      ("Plugin: %s"):format(row.name),
      ("Status: %s"):format(row.status),
      ("Risk:   %s"):format(risk_label(row)),
      ("Source: %s"):format(row.source or "-"),
      ("Repo:   %s"):format(row.repo_url or "-"),
      ("Diff:   %s"):format(row.diff_url or "-"),
      ("Current:%s"):format(" " .. (row.current_version or short_rev(row.rev_before) or short_rev(row.rev) or "-")),
      ("Target: %s"):format(row.target_version or short_rev(row.rev_after) or "-"),
      "",
      "Pending updates:",
    }
    vim.list_extend(lines, vim.split(pending, "\n", { trimempty = false }))
    lines[#lines + 1] = ""
    lines[#lines + 1] = "q / <Esc> close | o open diff | O open repo"

    details_bufnr = vim.api.nvim_create_buf(false, true)
    vim.bo[details_bufnr].buftype = "nofile"
    vim.bo[details_bufnr].bufhidden = "wipe"
    vim.bo[details_bufnr].buflisted = false
    vim.bo[details_bufnr].swapfile = false
    vim.bo[details_bufnr].filetype = "markdown"
    vim.api.nvim_buf_set_lines(details_bufnr, 0, -1, false, lines)
    vim.bo[details_bufnr].modifiable = false

    local editor_w = vim.o.columns
    local editor_h = vim.o.lines - vim.o.cmdheight
    local width = math.min(math.max(90, math.floor(editor_w * 0.75)), editor_w - 4)
    local height = math.min(math.max(22, math.floor(editor_h * 0.70)), editor_h - 4)
    local row_pos = math.floor((editor_h - height) / 2)
    local col_pos = math.floor((editor_w - width) / 2)

    details_winid = vim.api.nvim_open_win(details_bufnr, true, {
      relative = "editor",
      style = "minimal",
      border = "rounded",
      title = (" %s details "):format(row.name),
      title_pos = "center",
      row = row_pos,
      col = col_pos,
      width = width,
      height = height,
    })
    vim.wo[details_winid].wrap = true

    vim.keymap.set("n", "q", close_details_popup, { buffer = details_bufnr, nowait = true, silent = true })
    vim.keymap.set("n", "<Esc>", close_details_popup, { buffer = details_bufnr, nowait = true, silent = true })
    vim.keymap.set("n", "o", function()
      if row.diff_url then
        vim.ui.open(row.diff_url)
      else
        vim.notify("No diff URL for this plugin", vim.log.levels.WARN)
      end
    end, { buffer = details_bufnr, nowait = true, silent = true })
    vim.keymap.set("n", "O", function()
      if row.repo_url then
        vim.ui.open(row.repo_url)
      else
        vim.notify("No repo URL for this plugin", vim.log.levels.WARN)
      end
    end, { buffer = details_bufnr, nowait = true, silent = true })
  end

  local function render()
    ensure_dashboard_highlights()
    local mode = pack_report_cache.mode or "unknown"
    local stamp = pack_report_cache.updated_at and os.date("%H:%M:%S", pack_report_cache.updated_at) or "?"
    local counts = summary_counts()
    local visible = visible_rows()
    local sel_visible = selected_count(true)
    local sel_total = selected_count(false)
    local win_width = (winid and vim.api.nvim_win_is_valid(winid)) and vim.api.nvim_win_get_width(winid)
      or vim.o.columns
    local row_width = math.max(80, win_width - 2)
    local sep_char = use_nerd_font and "─" or "-"
    local sep = string.rep(sep_char, row_width)

    local title = use_nerd_font and "󰒲  vim.pack dashboard" or "vim.pack dashboard"
    local title_line =
      string.format("%s   mode:%s   refreshed:%s   selected:%d/%d", title, mode, stamp, sel_visible, sel_total)
    local stats_line
    if use_nerd_font then
      stats_line = string.format(
        "%s %d   %s %d   %s %d   %s %d   %s %d",
        icons.update,
        counts.update,
        icons.same,
        counts.same,
        icons.error,
        counts.error,
        icons.unknown,
        counts.unknown,
        icons.risk_break,
        counts.breaking
      )
    else
      stats_line = string.format(
        "updates:%d  same:%d  errors:%d  unknown:%d  breaking:%d",
        counts.update,
        counts.same,
        counts.error,
        counts.unknown,
        counts.breaking
      )
    end
    local controls_line = string.format(
      "r/R refresh  f filter:%s  s sort:%s  / search:%s  <Space> select  u/U update  o/O links  K details  ? help  (%s/%s)",
      filter_mode,
      sort_mode,
      search_text or "-",
      icons.link_diff,
      icons.link_repo
    )

    local name_col = 34
    local version_col = 26
    local links_col = 12
    local header_row = string.format(
      "SEL ST RK %-" .. name_col .. "s %-" .. version_col .. "s %-" .. links_col .. "s",
      "PLUGIN",
      "VERSION",
      "LINKS"
    )

    local lines = {
      title_line,
      stats_line,
      controls_line,
      sep,
      header_row,
      sep,
    }

    row_by_line = {}
    first_data_line = #lines + 1
    for _, row in ipairs(visible) do
      local sel = selected[row.name] and "[x]" or "[ ]"
      local icon = status_icon[row.status] or "?"
      local risk = risk_label(row)
      local name = truncate_cell(row.name, name_col)
      local version = truncate_cell(version_cell(row), version_col)
      local link = truncate_cell(links_cell(row), links_col)
      lines[#lines + 1] = string.format(
        "%-3s %-2s %-2s %-" .. name_col .. "s %-" .. version_col .. "s %-" .. links_col .. "s",
        sel,
        icon,
        risk,
        name,
        version,
        link
      )
      row_by_line[#lines] = row
    end
    if #visible == 0 then
      lines[#lines + 1] = "(No plugins match current filter/search)"
    end

    vim.bo[bufnr].modifiable = true
    vim.api.nvim_buf_set_lines(bufnr, 0, -1, false, lines)
    vim.bo[bufnr].modifiable = false

    vim.api.nvim_buf_clear_namespace(bufnr, dashboard_ns, 0, -1)
    local function hl_line(line_no, group)
      if line_no > 0 and line_no <= #lines then
        pcall(vim.api.nvim_buf_add_highlight, bufnr, dashboard_ns, group, line_no - 1, 0, -1)
      end
    end
    hl_line(1, "PackDashboardTitle")
    hl_line(2, "PackDashboardStats")
    hl_line(3, "PackDashboardMeta")
    hl_line(4, "PackDashboardMeta")
    hl_line(5, "PackDashboardHeader")
    hl_line(6, "PackDashboardMeta")

    local status_hl = {
      update = "PackDashboardStatusUpdate",
      same = "PackDashboardStatusSame",
      error = "PackDashboardStatusError",
      unknown = "PackDashboardStatusUnknown",
    }

    local row_count = 0
    for _ in pairs(row_by_line) do
      row_count = row_count + 1
    end

    -- Keep scrolling smooth on large plugin sets by trimming per-row decorations.
    local allow_row_highlights = not fast_scroll_mode or row_count <= 120
    if not allow_row_highlights then
      return
    end

    -- Row layout uses fixed-width columns. These byte offsets are stable:
    -- 0..2 = [ ]/[x], 4..5 = status, 7..8 = risk.
    local sel_start, sel_end = 0, 3
    local st_start, st_end = 4, 6
    local rk_start, rk_end = 7, 9

    for line_no, row in pairs(row_by_line) do
      if selected[row.name] then
        pcall(
          vim.api.nvim_buf_add_highlight,
          bufnr,
          dashboard_ns,
          "PackDashboardSelected",
          line_no - 1,
          sel_start,
          sel_end
        )
      end

      pcall(
        vim.api.nvim_buf_add_highlight,
        bufnr,
        dashboard_ns,
        status_hl[row.status] or "PackDashboardStatusUnknown",
        line_no - 1,
        st_start,
        st_end
      )

      local risk_group = "PackDashboardRiskUnknown"
      if row.breaking == true then
        risk_group = "PackDashboardRiskBreak"
      elseif row.breaking == false then
        risk_group = "PackDashboardRiskSafe"
      end
      if row.status == "update" then
        pcall(vim.api.nvim_buf_add_highlight, bufnr, dashboard_ns, risk_group, line_no - 1, rk_start, rk_end)
      end
    end
  end

  local function row_at_cursor()
    local line = vim.api.nvim_win_get_cursor(0)[1]
    return row_by_line[line]
  end

  local function refresh(next_online, names, merge)
    if scan_updates_to_cache(next_online, names, merge) then
      local current = row_at_cursor()
      local current_name = current and current.name or nil
      rows = collect_dashboard_rows()
      selected = {}
      if winid and vim.api.nvim_win_is_valid(winid) then
        vim.api.nvim_set_current_win(winid)
      end
      render()
      if current_name then
        for line, row in pairs(row_by_line) do
          if row.name == current_name then
            pcall(vim.api.nvim_win_set_cursor, 0, { line, 0 })
            break
          end
        end
      end
    end
  end

  local function update_by_names(names, empty_msg, noop_msg)
    if #names == 0 then
      vim.notify(empty_msg or "No plugins selected", vim.log.levels.WARN)
      return
    end

    local filtered = {}
    local seen = {}
    for _, name in ipairs(names) do
      if type(name) == "string" and name ~= "" and not seen[name] then
        seen[name] = true
        filtered[#filtered + 1] = name
      end
    end

    if #filtered == 0 then
      vim.notify(noop_msg or "Selected plugins are already up to date", vim.log.levels.INFO)
      return
    end

    vim.pack.update(filtered, { force = true })
    refresh(false, filtered, true)
  end

  local function close_dashboard()
    close_details_popup()
    if winid and vim.api.nvim_win_is_valid(winid) then
      pcall(vim.api.nvim_win_close, winid, true)
    else
      pcall(vim.api.nvim_buf_delete, bufnr, { force = true })
    end
  end

  vim.keymap.set("n", "q", close_dashboard, { buffer = bufnr, nowait = true, silent = true })
  vim.keymap.set("n", "<Esc>", close_dashboard, { buffer = bufnr, nowait = true, silent = true })
  vim.keymap.set("n", "gg", function()
    if next(row_by_line) == nil then
      return
    end
    pcall(vim.api.nvim_win_set_cursor, 0, { first_data_line, 0 })
  end, { buffer = bufnr, nowait = true, silent = true })
  vim.keymap.set("n", "r", function()
    refresh(true)
  end, { buffer = bufnr, nowait = true, silent = true })
  vim.keymap.set("n", "R", function()
    refresh(false)
  end, { buffer = bufnr, nowait = true, silent = true })

  vim.keymap.set("n", "<Space>", function()
    local row = row_at_cursor()
    if not row then
      return
    end
    selected[row.name] = not selected[row.name]
    render()
  end, { buffer = bufnr, nowait = true, silent = true })

  vim.keymap.set("n", "x", function()
    local row = row_at_cursor()
    if not row then
      return
    end
    selected[row.name] = not selected[row.name]
    render()
  end, { buffer = bufnr, nowait = true, silent = true })

  vim.keymap.set("n", "a", function()
    local visible = visible_rows()
    for _, row in ipairs(visible) do
      if row.status == "update" then
        selected[row.name] = true
      end
    end
    render()
  end, { buffer = bufnr, nowait = true, silent = true })

  vim.keymap.set("n", "A", function()
    selected = {}
    render()
  end, { buffer = bufnr, nowait = true, silent = true })

  vim.keymap.set("n", "<CR>", function()
    local row = row_at_cursor()
    if not row then
      return
    end
    update_by_names({ row.name }, "No plugin on current row", "Plugin is already up to date")
  end, { buffer = bufnr, nowait = true, silent = true })

  vim.keymap.set("n", "u", function()
    local names = selected_names(true)
    if #names == 0 then
      local current = row_at_cursor()
      if current then
        names = { current.name }
      end
    end
    update_by_names(names, "No selected plugins", "Selected plugins are already up to date")
  end, { buffer = bufnr, nowait = true, silent = true })

  vim.keymap.set("n", "U", function()
    local names = {}
    for _, row in ipairs(rows) do
      names[#names + 1] = row.name
    end
    update_by_names(names, "No plugins available to update", "All plugins are already up to date")
  end, { buffer = bufnr, nowait = true, silent = true })

  vim.keymap.set("n", "o", function()
    local row = row_at_cursor()
    if not row then
      return
    end
    if row.diff_url then
      vim.ui.open(row.diff_url)
      return
    end
    if row.repo_url then
      vim.notify("No direct compare URL; opening repository instead", vim.log.levels.INFO)
      vim.ui.open(row.repo_url)
      return
    end
    vim.notify("No diff/repo URL for this plugin", vim.log.levels.WARN)
  end, { buffer = bufnr, nowait = true, silent = true })

  vim.keymap.set("n", "d", function()
    local row = row_at_cursor()
    if not row then
      return
    end
    if row.diff_url then
      vim.ui.open(row.diff_url)
      return
    end
    if row.repo_url then
      vim.notify("No direct compare URL; opening repository instead", vim.log.levels.INFO)
      vim.ui.open(row.repo_url)
      return
    end
    vim.notify("No diff/repo URL for this plugin", vim.log.levels.WARN)
  end, { buffer = bufnr, nowait = true, silent = true })

  vim.keymap.set("n", "O", function()
    local row = row_at_cursor()
    if not row or not row.repo_url then
      vim.notify("No repo URL for this plugin", vim.log.levels.WARN)
      return
    end
    vim.ui.open(row.repo_url)
  end, { buffer = bufnr, nowait = true, silent = true })

  vim.keymap.set("n", "K", function()
    local row = row_at_cursor()
    if not row then
      return
    end
    open_details_popup(row)
  end, { buffer = bufnr, nowait = true, silent = true })

  vim.keymap.set("n", "T", function()
    local row = row_at_cursor()
    if row and row.name then
      vim.api.nvim_cmd({ cmd = "PackTrace", args = { row.name } }, {})
      return
    end
    vim.api.nvim_cmd({ cmd = "PackTrace" }, {})
  end, { buffer = bufnr, nowait = true, silent = true })

  vim.keymap.set("n", "f", function()
    cycle_filter_mode()
    render()
  end, { buffer = bufnr, nowait = true, silent = true })

  vim.keymap.set("n", "s", function()
    sort_mode = sort_mode == "status" and "name" or "status"
    render()
  end, { buffer = bufnr, nowait = true, silent = true })

  vim.keymap.set("n", "/", function()
    vim.ui.input({
      prompt = "Plugin search (name substring): ",
      default = search_text or "",
    }, function(input)
      if input == nil then
        return
      end
      local normalized = vim.trim(input)
      search_text = normalized ~= "" and normalized or nil
      if winid and vim.api.nvim_win_is_valid(winid) then
        vim.api.nvim_set_current_win(winid)
      end
      render()
    end)
  end, { buffer = bufnr, nowait = true, silent = true })

  vim.keymap.set("n", "c", function()
    search_text = nil
    render()
  end, { buffer = bufnr, nowait = true, silent = true })

  vim.keymap.set("n", "?", function()
    local help_lines = {
      "vim.pack dashboard keys",
      "",
      "q / <Esc>  close dashboard",
      "r / R      refresh online / offline",
      "f          cycle filter (all -> updates -> issues -> selected)",
      "s          cycle sort (status <-> name)",
      "/ / c      set search / clear search",
      "<Space>/x  toggle row selection",
      "a / A      select visible pending updates / clear all selection",
      "<CR>       update plugin at cursor",
      "u / U      update selected (or cursor if none) / update all listed",
      "o / d      open diff URL (fallback: repository)",
      "O          open repository URL",
      "K          open details popup",
      "T          open load trace (current plugin)",
    }
    local hbuf = vim.api.nvim_create_buf(false, true)
    vim.bo[hbuf].buftype = "nofile"
    vim.bo[hbuf].bufhidden = "wipe"
    vim.bo[hbuf].swapfile = false
    vim.api.nvim_buf_set_lines(hbuf, 0, -1, false, help_lines)
    vim.bo[hbuf].modifiable = false

    local editor_w = vim.o.columns
    local editor_h = vim.o.lines - vim.o.cmdheight
    local width = math.min(88, editor_w - 4)
    local height = math.min(#help_lines + 2, editor_h - 4)
    local hwin = vim.api.nvim_open_win(hbuf, true, {
      relative = "editor",
      style = "minimal",
      border = "rounded",
      title = " dashboard help ",
      title_pos = "center",
      row = math.floor((editor_h - height) / 2),
      col = math.floor((editor_w - width) / 2),
      width = width,
      height = height,
    })
    vim.keymap.set("n", "q", function()
      if hwin and vim.api.nvim_win_is_valid(hwin) then
        vim.api.nvim_win_close(hwin, true)
      end
    end, { buffer = hbuf, nowait = true, silent = true })
    vim.keymap.set("n", "<Esc>", function()
      if hwin and vim.api.nvim_win_is_valid(hwin) then
        vim.api.nvim_win_close(hwin, true)
      end
    end, { buffer = hbuf, nowait = true, silent = true })
  end, { buffer = bufnr, nowait = true, silent = true })

  open_popup_window()
  render()
end

function M.setup()
  if configured then
    return
  end
  configured = true

  vim.api.nvim_create_user_command("PackSync", function()
    vim.pack.update()
    refresh_pack_report_cache_from_current_buffer()
  end, {
    desc = "Check updates online (fetch remotes)",
  })

  vim.api.nvim_create_user_command("PackStatus", function()
    vim.pack.update(nil, { offline = true })
    refresh_pack_report_cache_from_current_buffer()
  end, {
    desc = "Show status from local refs only (offline)",
  })

  vim.api.nvim_create_user_command("PackDashboard", function(cmd)
    open_pack_dashboard(true, cmd.bang)
  end, {
    bang = true,
    desc = "Open vim.pack dashboard with update risk and diff links",
  })

  vim.api.nvim_create_user_command("PackMenu", function(cmd)
    open_pack_dashboard(true, cmd.bang)
  end, {
    bang = true,
    desc = "Open vim.pack dashboard (legacy alias)",
  })
end

return M
