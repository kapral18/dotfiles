local state = require("core.pack_dashboard.state")
local fmt = require("core.pack_dashboard.ui.format")
local rows = require("core.pack_dashboard.ui.rows")

local M = {}

local dashboard_ns = vim.api.nvim_create_namespace("core.pack_dashboard")

local function ensure_highlights()
  local set_hl = vim.api.nvim_set_hl
  set_hl(0, "PackDashboardTitle", { default = true, link = "Title" })
  set_hl(0, "PackDashboardStats", { default = true, link = "Special" })
  -- FILTERED banner: warning-styled and bold so a narrowed list is unmistakable.
  set_hl(0, "PackDashboardFiltered", { default = true, link = "WarningMsg", bold = true })
  -- Live refresh progress line: info-colored so it reads as active, not chrome.
  set_hl(0, "PackDashboardProgress", { default = true, link = "DiagnosticInfo" })
  -- Key-reference (help) line: a distinct accent so it does not blend into the
  -- grey meta lines as one undifferentiated blob.
  set_hl(0, "PackDashboardKey", { default = true, link = "Function" })
  set_hl(0, "PackDashboardMeta", { default = true, link = "Comment" })
  -- Field label (the `key` of a key:value pair): dim, so values stand out.
  set_hl(0, "PackDashboardLabel", { default = true, link = "Comment" })
  -- Field value: normal foreground so each value reads against its dim label.
  set_hl(0, "PackDashboardValue", { default = true, link = "Normal" })
  -- Inline item separator (the vertical bar between fields): faint chrome.
  set_hl(0, "PackDashboardBar", { default = true, link = "NonText" })
  -- Section divider rule: faint chrome, same family as the bar.
  set_hl(0, "PackDashboardRule", { default = true, link = "NonText" })
  set_hl(0, "PackDashboardHeader", { default = true, link = "Identifier" })
  set_hl(0, "PackDashboardStatusUpdate", { default = true, link = "DiagnosticInfo" })
  set_hl(0, "PackDashboardStatusSame", { default = true, link = "String" })
  set_hl(0, "PackDashboardStatusError", { default = true, link = "DiagnosticError" })
  set_hl(0, "PackDashboardStatusUnknown", { default = true, link = "Comment" })
  set_hl(0, "PackDashboardStatusOrphan", { default = true, link = "DiagnosticWarn" })
  set_hl(0, "PackDashboardStatusDrift", { default = true, link = "DiagnosticWarn" })
  set_hl(0, "PackDashboardStatusRisky", { default = true, link = "DiagnosticWarn" })
  set_hl(0, "PackDashboardRiskBreak", { default = true, link = "DiagnosticWarn" })
  set_hl(0, "PackDashboardRiskSafe", { default = true, link = "DiffAdd" })
  set_hl(0, "PackDashboardRiskUnknown", { default = true, link = "Comment" })
  set_hl(0, "PackDashboardLink", { default = true, link = "Underlined" })
  -- Checkbox only: bold cyan, no bg — avoid Visual (blue) and IncSearch/DiagnosticWarn (breaking orange).
  set_hl(0, "PackDashboardSelected", { default = true, link = "Special", bold = true })
end

-- last-result section as labeled key:value segments (label dim, value accented).
local function raw_status_segments(ctx)
  local raw = state.pack_report_cache.last_check_counts
  local segs
  if type(raw) == "table" then
    segs = {
      {
        key = "update",
        value = tostring(tonumber(raw.update) or 0),
        key_hl = "PackDashboardLabel",
        value_hl = "PackDashboardStatusUpdate",
      },
      {
        key = "same",
        value = tostring(tonumber(raw.same) or 0),
        key_hl = "PackDashboardLabel",
        value_hl = "PackDashboardStatusSame",
      },
      {
        key = "error",
        value = tostring(tonumber(raw.error) or 0),
        key_hl = "PackDashboardLabel",
        value_hl = "PackDashboardStatusError",
      },
    }
  else
    segs = { { text = "last-result: n/a (run r)", hl = "PackDashboardMeta" } }
  end
  segs[#segs + 1] = {
    key = "online",
    value = state.format_cache_stamp(state.pack_report_cache.last_online_at),
    key_hl = "PackDashboardLabel",
    value_hl = "PackDashboardValue",
  }
  segs[#segs + 1] = {
    key = "offline",
    value = state.format_cache_stamp(state.pack_report_cache.last_offline_at),
    key_hl = "PackDashboardLabel",
    value_hl = "PackDashboardValue",
  }
  return segs
end

-- Live progress for an in-flight refresh, on its own dedicated header line so it
-- stays visible in a narrow pane instead of being clipped off the right edge.
local function progress_segments(ctx)
  local progress = ctx.online_check_progress
  local detail
  if type(progress) == "table" and progress.phase == "status" then
    if tonumber(progress.total) and progress.total > 0 then
      detail = string.format("status %d/%d", tonumber(progress.done) or 0, progress.total)
    else
      detail = "status"
    end
  elseif type(progress) == "table" and tonumber(progress.total) and progress.total > 0 then
    detail = string.format("fetch %d/%d", tonumber(progress.done) or 0, progress.total)
  else
    detail = "starting…"
  end
  local marker = ctx.use_nerd_font and " " or ">>"
  return {
    {
      key = marker .. " checking updates",
      value = detail,
      key_hl = "PackDashboardProgress",
      value_hl = "PackDashboardValue",
    },
  }
end

-- Counts section: one segment per status, the COUNT colored by that status group
-- so each kind reads in its own tone even within the same line. Nerd-font uses
-- the status glyph as the label (space-separated from the count); ASCII uses a
-- short word label.
local function stats_segments(ctx, counts)
  local function seg(icon_key, ascii, count, value_hl)
    local label = ctx.use_nerd_font and ctx.icons[icon_key] or ascii
    local sep = ctx.use_nerd_font and " " or ":"
    return { key = label, value = tostring(count), sep = sep, key_hl = "PackDashboardLabel", value_hl = value_hl }
  end
  return {
    seg("update", "upd", counts.update, "PackDashboardStatusUpdate"),
    seg("same", "same", counts.same, "PackDashboardStatusSame"),
    seg("error", "err", counts.error, "PackDashboardStatusError"),
    seg("unknown", "unk", counts.unknown, "PackDashboardStatusUnknown"),
    seg("orphan", "orph", counts.orphan, "PackDashboardStatusOrphan"),
    seg("drift", "drift", counts.drift, "PackDashboardStatusDrift"),
    seg("risky", "risky", counts.risky, "PackDashboardStatusRisky"),
    seg("risk_break", "brk", counts.breaking, "PackDashboardRiskBreak"),
  }
end

local function join_cells(cells)
  local parts = {}
  local ranges = {}
  local byte_col = 0
  for _, cell in ipairs(cells) do
    if #parts > 0 then
      parts[#parts + 1] = " "
      byte_col = byte_col + 1
    end
    local start_col = byte_col
    parts[#parts + 1] = cell.text
    byte_col = byte_col + #cell.text
    if cell.key then
      ranges[cell.key] = { start_col = start_col, end_col = byte_col }
    end
  end
  return table.concat(parts), ranges
end

-- Column widths shared by the header and every data row so a single-row rewrite
-- aligns with the full-table render.
local NAME_COL, VERSION_COL, LINKS_COL = 34, 26, 12

-- The glyph shown in the status cell. While a row is mid-refresh
-- (`ctx.refreshing[name]`), it shows the animated spinner frame instead of the
-- cached status icon so each row advertises its own in-flight state.
local function status_cell_text(ctx, row)
  if ctx.refreshing and ctx.refreshing[row.name] then
    local frames = ctx.spinner_frames or { "|", "/", "-", "\\" }
    local frame = frames[((ctx.spinner_frame or 0) % #frames) + 1]
    return fmt.pad_cell(frame, 2)
  end
  return fmt.pad_cell(ctx.status_icon[row.status] or "?", 2)
end

-- Build the buffer line + cell byte ranges for a single data row. Used by both
-- the full-table builder and the per-row in-place updater.
local function build_row_line(ctx, row)
  return join_cells({
    { key = "sel", text = fmt.pad_cell(ctx.selected[row.name] and "[x]" or "[ ]", 3) },
    { key = "status", text = status_cell_text(ctx, row) },
    { key = "risk", text = fmt.pad_cell(fmt.risk_label(ctx, row), 2) },
    { text = fmt.pad_cell(row.name, NAME_COL) },
    { text = fmt.pad_cell(fmt.version_cell(row), VERSION_COL) },
    { text = fmt.pad_cell(fmt.links_cell(ctx, row), LINKS_COL) },
  })
end

local status_hl = {
  update = "PackDashboardStatusUpdate",
  same = "PackDashboardStatusSame",
  error = "PackDashboardStatusError",
  unknown = "PackDashboardStatusUnknown",
  orphan = "PackDashboardStatusOrphan",
  drift = "PackDashboardStatusDrift",
  risky = "PackDashboardStatusRisky",
}

-- Apply the selection/status/risk extmarks for a single data row at `line_no`
-- (1-based). Shared by the full-table and per-row render paths.
local function apply_row_highlights(ctx, line_no, row, ranges)
  ranges = ranges or {}
  if ctx.selected[row.name] and ranges.sel then
    pcall(vim.api.nvim_buf_set_extmark, ctx.bufnr, dashboard_ns, line_no - 1, ranges.sel.start_col, {
      hl_group = "PackDashboardSelected",
      end_col = ranges.sel.end_col,
    })
  end
  if ranges.status then
    local group = (ctx.refreshing and ctx.refreshing[row.name]) and "PackDashboardStatusUnknown"
      or (status_hl[row.status] or "PackDashboardStatusUnknown")
    pcall(vim.api.nvim_buf_set_extmark, ctx.bufnr, dashboard_ns, line_no - 1, ranges.status.start_col, {
      hl_group = group,
      end_col = ranges.status.end_col,
    })
  end
  if row.status == "update" and not (ctx.refreshing and ctx.refreshing[row.name]) then
    local risk_group = row.breaking == true and "PackDashboardRiskBreak"
      or (row.breaking == false and "PackDashboardRiskSafe" or "PackDashboardRiskUnknown")
    if ranges.risk then
      pcall(vim.api.nvim_buf_set_extmark, ctx.bufnr, dashboard_ns, line_no - 1, ranges.risk.start_col, {
        hl_group = risk_group,
        end_col = ranges.risk.end_col,
      })
    end
  end
end

-- Word-wrap `text` into lines no wider than `width` display columns, breaking on
-- spaces. A token longer than `width` is emitted on its own (over-long) line
-- rather than split mid-word. Always returns at least one line.
local function wrap_text(text, width)
  if width < 1 then
    return { text }
  end
  local lines = {}
  local current = ""
  for token in text:gmatch("%S+") do
    if current == "" then
      current = token
    elseif vim.fn.strdisplaywidth(current .. " " .. token) <= width then
      current = current .. " " .. token
    else
      lines[#lines + 1] = current
      current = token
    end
  end
  lines[#lines + 1] = current
  return lines
end

-- The vertical bar that separates inline items within a header section, and the
-- horizontal rule character that separates sections. Nerd-font uses box-drawing;
-- ASCII falls back to pipe/dash.
local function section_bar(use_nerd_font)
  return use_nerd_font and "│" or "|"
end

-- Render one segment to its display text and the relative byte spans coloring
-- its parts. A segment is one of:
--   { text = "...", hl = "Group" }                       -- a plain item
--   { key = "mode", value = "online",                    -- a key:value item
--     key_hl = "G1", value_hl = "G2", sep = ":" }         -- (sep defaults ":")
-- Returns `text, spans` where spans are `{start_col,end_col,hl}` (0-based, byte)
-- relative to the start of this segment's text.
local function render_segment(seg)
  if seg.key ~= nil then
    local sep = seg.sep or ":"
    local key = tostring(seg.key)
    local value = tostring(seg.value)
    local text = key .. sep .. value
    local spans = {
      { start_col = 0, end_col = #key, hl = seg.key_hl },
    }
    local value_start = #key + #sep
    spans[#spans + 1] = { start_col = value_start, end_col = value_start + #value, hl = seg.value_hl }
    return text, spans
  end
  local text = seg.text or ""
  return text, { { start_col = 0, end_col = #text, hl = seg.hl } }
end

-- Lay out a list of segments (see render_segment) into one or more buffer lines
-- no wider than `width`, joined by " <bar> " separators, emitting per-line byte
-- spans for highlighting. A section wraps at a segment boundary: when the next
-- segment (plus its leading bar) would overflow, the line breaks and the segment
-- starts the next line — so a `key:value` item is never split mid-token. A lone
-- segment wider than `width` is placed on its own line (clipped only by the
-- window, never mid-render). Returns `{ lines = {string,...}, spans = { [i] =
-- { {start_col,end_col,hl}, ... } } }` (byte offsets, 0-based start col).
local function layout_segments(segments, width, bar_hl, use_nerd_font)
  local bar = section_bar(use_nerd_font)
  local joiner = " " .. bar .. " "
  local out_lines = {}
  local out_spans = {}

  local cur_text = ""
  local cur_spans = {}

  local function flush()
    out_lines[#out_lines + 1] = cur_text
    out_spans[#out_spans + 1] = cur_spans
    cur_text = ""
    cur_spans = {}
  end

  local function add_spans_at(offset, spans)
    for _, s in ipairs(spans) do
      cur_spans[#cur_spans + 1] = { start_col = offset + s.start_col, end_col = offset + s.end_col, hl = s.hl }
    end
  end

  for _, seg in ipairs(segments) do
    local text, spans = render_segment(seg)
    if text ~= "" then
      if cur_text == "" then
        add_spans_at(0, spans)
        cur_text = text
      else
        local candidate = cur_text .. joiner .. text
        if vim.fn.strdisplaywidth(candidate) <= width then
          local bar_start = #cur_text + 1 -- one byte for the leading space
          cur_spans[#cur_spans + 1] = { start_col = bar_start, end_col = bar_start + #bar, hl = bar_hl }
          add_spans_at(#cur_text + #joiner, spans)
          cur_text = candidate
        else
          flush()
          add_spans_at(0, spans)
          cur_text = text
        end
      end
    end
  end
  if cur_text ~= "" or #out_lines == 0 then
    flush()
  end

  return { lines = out_lines, spans = out_spans }
end

-- True when the current filter mode and/or search text is hiding rows, i.e. the
-- visible set is a strict subset of the loaded set. Drives the FILTERED banner.
local function filter_is_active(ctx)
  return ctx.filter_mode ~= "all" or (type(ctx.search_text) == "string" and ctx.search_text ~= "")
end

-- One human-readable description of every active narrowing facet, e.g.
-- "filter:updates, search:'treesitter'". Returns nil when nothing is narrowing.
local function active_filter_desc(ctx)
  local parts = {}
  if ctx.filter_mode ~= "all" then
    parts[#parts + 1] = "filter:" .. ctx.filter_mode
  end
  if type(ctx.search_text) == "string" and ctx.search_text ~= "" then
    parts[#parts + 1] = "search:'" .. ctx.search_text .. "'"
  end
  if #parts == 0 then
    return nil
  end
  return table.concat(parts, ", ")
end

-- Build the keymap-help section as key:value segments. Each entry is one
-- `<keys> <action>` item: the keys take an accent color, the action stays dim,
-- and items are bar-separated like every other section.
local function help_segments(ctx)
  local function item(keys, action)
    return { key = keys, value = action, sep = " ", key_hl = "PackDashboardKey", value_hl = "PackDashboardMeta" }
  end
  return {
    item("r", "online-refresh"),
    item("R", "offline-status"),
    item("<CR>/u/U", "update-pending"),
    item("C", "clean-orphans"),
    item("V", "heal-drift"),
    { key = "f filter", value = ctx.filter_mode, key_hl = "PackDashboardKey", value_hl = "PackDashboardValue" },
    { key = "s sort", value = ctx.sort_mode, key_hl = "PackDashboardKey", value_hl = "PackDashboardValue" },
    { key = "/ search", value = ctx.search_text or "-", key_hl = "PackDashboardKey", value_hl = "PackDashboardValue" },
    item("a", "sel-all"),
    item("o", "link"),
    item("K", "details"),
    item("?", "help"),
  }
end

-- The header is variable-height and section-structured: each metadata section
-- (title, optional FILTERED banner, counts, optional live progress, last-result,
-- key help) is laid out as bar-separated `key:value` segments that wrap at
-- segment boundaries to the window width (never clipped), and consecutive
-- sections are divided by a thin horizontal rule. Returns `lines` plus a
-- parallel `line_spans` list (`line_spans[i]` = `{ {start_col,end_col,hl}, ...}`)
-- so the full render and the live-progress (render_header) path agree on the
-- exact header region — and its per-segment colors — without a hardcoded count.
local function build_header_lines(ctx)
  local counts = rows.summary_counts(ctx)
  local sel_visible = rows.selected_count(ctx, true)
  local sel_total = rows.selected_count(ctx, false)
  local visible_count = #rows.visible(ctx)
  local total_count = #(ctx.rows or {})
  local title = ctx.use_nerd_font and "󰒲  vim.pack dashboard" or "vim.pack dashboard"
  local win_width = (ctx.winid and vim.api.nvim_win_is_valid(ctx.winid)) and vim.api.nvim_win_get_width(ctx.winid)
    or vim.o.columns
  local row_width = math.max(80, win_width - 2)
  local full_rule = string.rep(ctx.use_nerd_font and "─" or "-", row_width)
  -- A lighter mid-rule between metadata sections (distinct from the heavy table
  -- separators below the column header).
  local section_rule = string.rep(ctx.use_nerd_font and "╌" or "·", row_width)

  local lines = {}
  local line_spans = {}

  local function push_raw(text, hl)
    lines[#lines + 1] = text
    line_spans[#line_spans + 1] = { { start_col = 0, end_col = #text, hl = hl } }
  end

  -- Emit a section: lay its segments out (bar-separated, wrapped) and append the
  -- resulting lines + spans. Within-section items are divided by colored bars and
  -- each section by its own color; an explicit `push_rule()` divides the larger
  -- blocks (status vs help) so the header stays compact instead of carrying a
  -- rule between every section.
  local function push_section(segments)
    local laid = layout_segments(segments, row_width, "PackDashboardBar", ctx.use_nerd_font)
    for i, l in ipairs(laid.lines) do
      lines[#lines + 1] = l
      line_spans[#line_spans + 1] = laid.spans[i]
    end
  end

  local function push_rule()
    push_raw(section_rule, "PackDashboardRule")
  end

  -- Title section: the name plus mode/result/applied/selected as colored fields.
  push_section({
    { text = title, hl = "PackDashboardTitle" },
    {
      key = "mode",
      value = state.pack_report_cache.mode or "unknown",
      key_hl = "PackDashboardLabel",
      value_hl = "PackDashboardValue",
    },
    {
      key = "result",
      value = state.format_cache_stamp(state.pack_report_cache.updated_at),
      key_hl = "PackDashboardLabel",
      value_hl = "PackDashboardValue",
    },
    {
      key = "applied",
      value = string.format(
        "%s (%d)",
        state.format_cache_stamp(state.pack_report_cache.last_applied_at),
        tonumber(state.pack_report_cache.last_applied_count) or 0
      ),
      key_hl = "PackDashboardLabel",
      value_hl = "PackDashboardValue",
    },
    {
      key = "selected",
      value = string.format("%d/%d", sel_visible, sel_total),
      key_hl = "PackDashboardLabel",
      value_hl = "PackDashboardValue",
    },
  })

  -- Unmistakable FILTERED banner when rows are hidden, so a narrowed list never
  -- looks like "only N plugins exist".
  if filter_is_active(ctx) then
    local marker = ctx.use_nerd_font and " FILTERED" or "[!] FILTERED"
    push_section({
      { text = marker, hl = "PackDashboardFiltered" },
      {
        key = "showing",
        value = string.format("%d of %d", visible_count, total_count),
        key_hl = "PackDashboardLabel",
        value_hl = "PackDashboardFiltered",
      },
      { text = active_filter_desc(ctx) or "-", hl = "PackDashboardValue" },
      { text = "f cycles filter, c clears search", hl = "PackDashboardMeta" },
    })
  end

  push_section(stats_segments(ctx, counts))
  push_section(raw_status_segments(ctx))

  -- Live refresh progress sits on its own line BELOW the whole status block
  -- (after both count rows) so it never splits the icon-counts row from the
  -- labeled-counts row; it stays just above the status->help rule.
  if ctx.online_check_running then
    push_section(progress_segments(ctx))
  end

  -- One rule divides the status block (state) from the help block (actions).
  push_rule()
  push_section(help_segments(ctx))

  -- Heavy table frame: column header bracketed by full-width rules. Kept as
  -- single lines (not wrapped) so they align with the horizontally-scrolling
  -- data rows below.
  push_raw(full_rule, "PackDashboardMeta")
  push_raw(
    table.concat({
      fmt.pad_cell("SEL", 3),
      fmt.pad_cell("ST", 2),
      fmt.pad_cell("RK", 2),
      fmt.pad_cell("PLUGIN", NAME_COL),
      fmt.pad_cell("VERSION", VERSION_COL),
      fmt.pad_cell("LINKS", LINKS_COL),
    }, " "),
    "PackDashboardHeader"
  )
  push_raw(full_rule, "PackDashboardMeta")

  return lines, line_spans
end

local function build_lines(ctx)
  local visible = rows.visible(ctx)
  local lines, header_spans = build_header_lines(ctx)
  ctx.header_spans = header_spans
  ctx.header_line_count = #lines

  ctx.row_by_line = {}
  ctx.row_ranges_by_line = {}
  ctx.line_by_name = {}
  ctx.first_data_line = #lines + 1
  for _, row in ipairs(visible) do
    local line, ranges = build_row_line(ctx, row)
    lines[#lines + 1] = line
    ctx.row_by_line[#lines] = row
    ctx.row_ranges_by_line[#lines] = ranges
    ctx.line_by_name[row.name] = #lines
  end
  if #visible == 0 then
    -- Distinguish "nothing installed" from "everything filtered out": when a
    -- filter is active, say so and point at the keys that reset it.
    if filter_is_active(ctx) and (#(ctx.rows or {}) > 0) then
      lines[#lines + 1] = string.format(
        "(0 of %d shown — %s hides the rest; press c to clear search, f to cycle filter)",
        #(ctx.rows or {}),
        active_filter_desc(ctx) or "filter"
      )
    else
      lines[#lines + 1] = "(No plugins match current filter/search)"
    end
  end
  return lines
end

-- Highlight the header region by applying the per-line byte spans produced with
-- the header lines. Line-count-agnostic so it stays correct as sections wrap to
-- a variable number of lines, and segment-level so each key/value/bar carries
-- its own color. Spans are clamped to the line length defensively.
local function highlight_static_headers(bufnr, lines, line_spans)
  if type(line_spans) ~= "table" then
    return
  end
  for line_no, spans in ipairs(line_spans) do
    local line = lines[line_no]
    if type(line) == "string" and type(spans) == "table" then
      local maxcol = #line
      for _, span in ipairs(spans) do
        if span.hl and span.start_col and span.end_col then
          local s = math.max(0, math.min(span.start_col, maxcol))
          local e = math.max(s, math.min(span.end_col, maxcol))
          if e > s then
            pcall(vim.api.nvim_buf_set_extmark, bufnr, dashboard_ns, line_no - 1, s, {
              hl_group = span.hl,
              end_col = e,
            })
          end
        end
      end
    end
  end
end

local function highlight_rows(ctx)
  local row_count = 0
  for _ in pairs(ctx.row_by_line) do
    row_count = row_count + 1
  end
  if ctx.fast_scroll_mode and row_count > 120 then
    return
  end

  for line_no, row in pairs(ctx.row_by_line) do
    apply_row_highlights(ctx, line_no, row, ctx.row_ranges_by_line and ctx.row_ranges_by_line[line_no])
  end
end

-- Rewrite a single plugin's row in place: update only that buffer line and its
-- extmarks, leaving every other row untouched. No effect when the row is not
-- currently visible (e.g. filtered out) or its line is unknown. This is the
-- per-row update path used while the refresh pipeline resolves plugins one by
-- one, so each row's status flips independently without a full-table redraw.
function M.render_row(ctx, name)
  if not (ctx.bufnr and vim.api.nvim_buf_is_valid(ctx.bufnr)) then
    return
  end
  local line_no = ctx.line_by_name and ctx.line_by_name[name]
  if not line_no then
    return
  end
  local row = ctx.row_by_line and ctx.row_by_line[line_no]
  if not row then
    return
  end

  ensure_highlights()
  local line, ranges = build_row_line(ctx, row)
  ctx.row_ranges_by_line[line_no] = ranges
  vim.bo[ctx.bufnr].modifiable = true
  pcall(vim.api.nvim_buf_set_lines, ctx.bufnr, line_no - 1, line_no, false, { line })
  vim.bo[ctx.bufnr].modifiable = false
  pcall(vim.api.nvim_buf_clear_namespace, ctx.bufnr, dashboard_ns, line_no - 1, line_no)
  apply_row_highlights(ctx, line_no, row, ranges)
end

-- Rewrite only the header lines (title/banner/stats/progress/keys/columns)
-- without touching the data rows. Used to keep the live `check:status:done/total`
-- progress counter current during an incremental refresh without redrawing the
-- whole table. The header is variable-height (wrapped help + optional FILTERED
-- banner): if the rebuilt header has a different line count than the one
-- currently in the buffer, fall back to a full render so the data rows below are
-- not clipped or duplicated.
function M.render_header(ctx)
  if not (ctx.bufnr and vim.api.nvim_buf_is_valid(ctx.bufnr)) then
    return
  end
  local prev_count = ctx.header_line_count
  local header, header_spans = build_header_lines(ctx)
  if type(prev_count) ~= "number" or #header ~= prev_count then
    M.render(ctx)
    return
  end
  ensure_highlights()
  vim.bo[ctx.bufnr].modifiable = true
  pcall(vim.api.nvim_buf_set_lines, ctx.bufnr, 0, prev_count, false, header)
  vim.bo[ctx.bufnr].modifiable = false
  pcall(vim.api.nvim_buf_clear_namespace, ctx.bufnr, dashboard_ns, 0, prev_count)
  ctx.header_spans = header_spans
  highlight_static_headers(ctx.bufnr, header, header_spans)
end

function M.render(ctx)
  if not vim.api.nvim_buf_is_valid(ctx.bufnr) then
    return
  end
  ensure_highlights()
  local lines = build_lines(ctx)
  vim.bo[ctx.bufnr].modifiable = true
  vim.api.nvim_buf_set_lines(ctx.bufnr, 0, -1, false, lines)
  vim.bo[ctx.bufnr].modifiable = false
  vim.api.nvim_buf_clear_namespace(ctx.bufnr, dashboard_ns, 0, -1)
  highlight_static_headers(ctx.bufnr, lines, ctx.header_spans)
  highlight_rows(ctx)
end

return M
