local state = require("core.pack_dashboard.state")
local analysis = require("core.pack_dashboard.analysis")
local fmt = require("core.pack_dashboard.ui.format")

local M = {}

local details_ns = vim.api.nvim_create_namespace("core.pack_dashboard.details")

local function ensure_details_highlights()
  vim.api.nvim_set_hl(0, "PackDashboardRiskBreak", { default = true, link = "DiagnosticWarn" })
end

local function has_breaking_signal(line)
  local summary = analysis.classify_commit_signals(line)
  return type(summary) == "table" and summary.has_breaking == true
end

function M.close_details(ctx)
  if ctx.details_winid and vim.api.nvim_win_is_valid(ctx.details_winid) then
    pcall(vim.api.nvim_win_close, ctx.details_winid, true)
  end
  if ctx.details_bufnr and vim.api.nvim_buf_is_valid(ctx.details_bufnr) then
    pcall(vim.api.nvim_buf_delete, ctx.details_bufnr, { force = true })
  end
  ctx.details_winid = nil
  ctx.details_bufnr = nil
end

function M.open_details(ctx, row)
  if not row then
    return
  end
  M.close_details(ctx)
  local pending = row.pending_updates
  if type(pending) ~= "string" or pending == "" then
    pending = "(No pending update details available)"
  end

  local breaking_lines = {}
  local lines = {
    ("Plugin: %s"):format(row.name),
    ("Status: %s"):format(row.status),
    ("Risk:   %s"):format(fmt.risk_label(ctx, row)),
    ("Risk reason: %s"):format(row.risk_reason or "-"),
    ("Semver delta: %s"):format(row.semver_delta or "n/a"),
    ("Commit signals: %s"):format(row.commit_signal or "none"),
    ("Source: %s"):format(row.source or "-"),
    ("Repo:   %s"):format(row.repo_url or "-"),
    ("Diff:   %s"):format(row.diff_url or "-"),
    ("Current:%s"):format(
      " " .. (row.current_version or analysis.short_rev(row.rev_before) or analysis.short_rev(row.rev) or "-")
    ),
    ("Target: %s"):format(row.target_version or analysis.short_rev(row.rev_after) or "-"),
    "",
    "Pending updates:",
  }
  for _, line in ipairs(vim.split(pending, "\n", { trimempty = false })) do
    lines[#lines + 1] = line
    if has_breaking_signal(line) then
      breaking_lines[#lines] = true
    end
  end

  local p_cache = state.pack_report_cache.plugins[row.name]
  local p_path = p_cache and p_cache.path
  if row.status == "update" and p_path and row.rev_before and row.rev_after then
    local subjects = analysis.commit_subjects_between(p_path, row.rev_before, row.rev_after)
    if subjects and #subjects > 0 then
      lines[#lines + 1] = ""
      local max_shown = 30
      local shown = math.min(#subjects, max_shown)
      lines[#lines + 1] = string.format("Changelog (%d commit%s):", #subjects, #subjects == 1 and "" or "s")
      for i = 1, shown do
        local line = "  " .. subjects[i]
        lines[#lines + 1] = line
        if has_breaking_signal(subjects[i]) then
          breaking_lines[#lines] = true
        end
      end
      if #subjects > max_shown then
        lines[#lines + 1] = string.format("  ... and %d more", #subjects - max_shown)
      end
    end
  end

  lines[#lines + 1] = ""
  lines[#lines + 1] = "q / <Esc> close | o open diff | O open repo"

  ctx.details_bufnr = vim.api.nvim_create_buf(false, true)
  vim.bo[ctx.details_bufnr].buftype = "nofile"
  vim.bo[ctx.details_bufnr].bufhidden = "wipe"
  vim.bo[ctx.details_bufnr].buflisted = false
  vim.bo[ctx.details_bufnr].swapfile = false
  vim.bo[ctx.details_bufnr].filetype = "markdown"
  vim.api.nvim_buf_set_lines(ctx.details_bufnr, 0, -1, false, lines)
  vim.bo[ctx.details_bufnr].modifiable = false
  ensure_details_highlights()
  for line_no in pairs(breaking_lines) do
    local line = lines[line_no] or ""
    pcall(vim.api.nvim_buf_set_extmark, ctx.details_bufnr, details_ns, line_no - 1, 0, {
      hl_group = "PackDashboardRiskBreak",
      end_col = #line,
      priority = 200,
    })
  end

  local editor_w = vim.o.columns
  local editor_h = vim.o.lines - vim.o.cmdheight
  local width = math.min(math.max(90, math.floor(editor_w * 0.75)), editor_w - 4)
  local height = math.min(math.max(22, math.floor(editor_h * 0.70)), editor_h - 4)
  ctx.details_winid = vim.api.nvim_open_win(ctx.details_bufnr, true, {
    relative = "editor",
    style = "minimal",
    border = "rounded",
    title = (" %s details "):format(row.name),
    title_pos = "center",
    row = math.floor((editor_h - height) / 2),
    col = math.floor((editor_w - width) / 2),
    width = width,
    height = height,
  })
  vim.wo[ctx.details_winid].wrap = true

  vim.keymap.set("n", "q", function()
    M.close_details(ctx)
  end, { buffer = ctx.details_bufnr, nowait = true, silent = true })
  vim.keymap.set("n", "<Esc>", function()
    M.close_details(ctx)
  end, { buffer = ctx.details_bufnr, nowait = true, silent = true })
  vim.keymap.set("n", "o", function()
    if row.diff_url then
      vim.ui.open(row.diff_url)
    else
      vim.notify("No diff URL for this plugin", vim.log.levels.WARN)
    end
  end, { buffer = ctx.details_bufnr, nowait = true, silent = true })
  vim.keymap.set("n", "O", function()
    if row.repo_url then
      vim.ui.open(row.repo_url)
    else
      vim.notify("No repo URL for this plugin", vim.log.levels.WARN)
    end
  end, { buffer = ctx.details_bufnr, nowait = true, silent = true })
end

function M.open_help()
  local help_lines = {
    "vim.pack dashboard keys",
    "",
    "q / <Esc>  close dashboard",
    "r          refresh online (fetches remotes)",
    "R          offline status (no fetch; may not show remote updates)",
    "f          cycle filter (all -> updates -> issues -> selected)",
    "s          cycle sort (status <-> name)",
    "/ / c      set search / clear search",
    "<Space>/x  toggle row selection (also works in visual mode)",
    "a / A      select all visible / clear all selection",
    "<CR>       update plugin at cursor",
    "u / U      update pending selected (or cursor if none) / all pending listed",
    "C          clean orphan plugins (selected orphans, else all orphans)",
    "V          heal drift: re-checkout drifted plugins to spec version (offline)",
    "o          open diff URL (fallback: repository)",
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
  local close = function()
    if hwin and vim.api.nvim_win_is_valid(hwin) then
      vim.api.nvim_win_close(hwin, true)
    end
  end
  vim.keymap.set("n", "q", close, { buffer = hbuf, nowait = true, silent = true })
  vim.keymap.set("n", "<Esc>", close, { buffer = hbuf, nowait = true, silent = true })
end

return M
