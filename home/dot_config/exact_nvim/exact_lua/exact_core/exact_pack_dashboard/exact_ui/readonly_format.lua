local analysis = require("core.pack_dashboard.analysis")

local M = {}

M.status_rank = { drift = 1, orphan = 2, risky = 3, error = 4, update = 5, same = 6, unknown = 7 }
M.filter_modes = { "all", "updates", "issues", "selected" }

function M.icons(use_nerd_font)
  if use_nerd_font then
    return {
      update = "",
      same = "",
      error = "",
      unknown = "",
      orphan = "\u{f1f8}",
      drift = "\u{f0e2}",
      risky = "\u{f071}",
      risk_break = "!",
      risk_safe = "+",
      risk_unknown = "-",
      link_diff = "diff",
      link_repo = "repo",
    }
  end
  return {
    update = "U",
    same = "=",
    error = "!",
    unknown = "?",
    orphan = "O",
    drift = "D",
    risky = "W",
    risk_break = "!",
    risk_safe = "+",
    risk_unknown = "-",
    link_diff = "diff",
    link_repo = "repo",
  }
end

function M.status_icons(icons)
  return {
    update = icons.update,
    same = icons.same,
    error = icons.error,
    unknown = icons.unknown,
    orphan = icons.orphan,
    drift = icons.drift,
    risky = icons.risky,
  }
end

function M.risk_label(ctx, row)
  if row.status ~= "update" then
    return "-"
  end
  if row.breaking == true then
    return ctx.icons.risk_break
  end
  if row.breaking == false then
    return ctx.icons.risk_safe
  end
  return ctx.icons.risk_unknown
end

function M.links_cell(ctx, row)
  if row.diff_url then
    return ctx.icons.link_diff
  end
  if row.repo_url then
    return ctx.icons.link_repo
  end
  return "-"
end

function M.truncate_display(text, max_width)
  if type(text) ~= "string" then
    text = tostring(text or "")
  end
  if max_width <= 0 then
    return ""
  end
  if vim.fn.strdisplaywidth(text) <= max_width then
    return text
  end

  local ellipsis = "…"
  if max_width == 1 then
    return ellipsis
  end

  local out = ""
  for _, ch in ipairs(vim.fn.split(text, "\\zs")) do
    local candidate = out .. ch
    if vim.fn.strdisplaywidth(candidate .. ellipsis) > max_width then
      break
    end
    out = candidate
  end
  return out .. ellipsis
end

function M.pad_cell(text, width)
  local value = M.truncate_display(text, width)
  local pad = width - vim.fn.strdisplaywidth(value)
  if pad <= 0 then
    return value
  end
  return value .. string.rep(" ", pad)
end

function M.version_cell(row)
  local current = row.current_version or analysis.short_rev(row.rev_before) or analysis.short_rev(row.rev)
  local target = row.target_version or analysis.short_rev(row.rev_after)
  if row.status == "update" then
    return (current or "-") .. " -> " .. (target or "-")
  end
  return current or "-"
end

return M
