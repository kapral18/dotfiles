local M = {}

local function has_breaking_marker(line)
  return line:find("breaking change", 1, true)
    or line:find("breaking:", 1, true)
    or line:find("!:", 1, true)
    or line:match("%f[%w]break:")
    or line:match("%f[%w]break%([^)]*%):")
end

local function classify_commit_signals(text)
  local summary = {
    has_breaking = false,
    has_deprecation = false,
    feat = 0,
    fix = 0,
    refactor = 0,
    perf = 0,
    docs = 0,
    chore = 0,
  }
  if type(text) ~= "string" or text == "" then
    return summary
  end

  for _, raw in ipairs(vim.split(text, "\n", { trimempty = true })) do
    local line = vim.trim(raw):lower()
    if line ~= "" then
      if has_breaking_marker(line) then
        summary.has_breaking = true
      end
      if line:find("deprecat", 1, true) then
        summary.has_deprecation = true
      end
      if line:match("^feat[%(:!]") or line:find(" feature", 1, true) then
        summary.feat = summary.feat + 1
      end
      if line:match("^fix[%(:!]") or line:find(" bugfix", 1, true) then
        summary.fix = summary.fix + 1
      end
      if line:match("^refactor[%(:!]") then
        summary.refactor = summary.refactor + 1
      end
      if line:match("^perf[%(:!]") or line:find(" performance", 1, true) then
        summary.perf = summary.perf + 1
      end
      if line:match("^docs[%(:!]") then
        summary.docs = summary.docs + 1
      end
      if line:match("^chore[%(:!]") then
        summary.chore = summary.chore + 1
      end
    end
  end

  return summary
end

local function format_commit_signals(summary)
  if type(summary) ~= "table" then
    return "none"
  end
  local parts = {}
  if summary.has_breaking then
    parts[#parts + 1] = "breaking"
  end
  if summary.has_deprecation then
    parts[#parts + 1] = "deprecation"
  end
  if (summary.feat or 0) > 0 then
    parts[#parts + 1] = "feat:" .. tostring(summary.feat)
  end
  if (summary.fix or 0) > 0 then
    parts[#parts + 1] = "fix:" .. tostring(summary.fix)
  end
  if (summary.refactor or 0) > 0 then
    parts[#parts + 1] = "refactor:" .. tostring(summary.refactor)
  end
  if (summary.perf or 0) > 0 then
    parts[#parts + 1] = "perf:" .. tostring(summary.perf)
  end
  if (summary.docs or 0) > 0 then
    parts[#parts + 1] = "docs:" .. tostring(summary.docs)
  end
  if (summary.chore or 0) > 0 then
    parts[#parts + 1] = "chore:" .. tostring(summary.chore)
  end
  if #parts == 0 then
    return "none"
  end
  return table.concat(parts, ", ")
end

M.classify_commit_signals = classify_commit_signals
M.format_commit_signals = format_commit_signals

return M
