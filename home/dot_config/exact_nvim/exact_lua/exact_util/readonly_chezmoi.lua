--- Chezmoi template helpers for Neovim integrations
local M = {}

local placeholder_prefix = "__CHEZMOI_TMPL_"

local function has_template_syntax(text)
  return text:find("{{", 1, true) ~= nil
end

--- Replace Go template markers with safe placeholders.
---@param text string
---@return string sanitized
---@return table<string, string> replacements
function M.mask_template(text)
  if not has_template_syntax(text) then
    return text, {}
  end

  local sanitized_parts = {}
  local replacements = {}
  local idx = 1
  local counter = 0

  while true do
    local start_pos = text:find("{{", idx, true)
    if not start_pos then
      table.insert(sanitized_parts, text:sub(idx))
      break
    end

    local end_pos = text:find("}}", start_pos + 2, true)
    if not end_pos then
      table.insert(sanitized_parts, text:sub(idx))
      break
    end

    table.insert(sanitized_parts, text:sub(idx, start_pos - 1))

    counter = counter + 1
    local original = text:sub(start_pos, end_pos + 1)

    local preceding_segment = text:sub(idx, start_pos - 1)
    local prefix = preceding_segment:match("([^\n]*)$") or ""
    local following_segment = text:sub(end_pos + 2)
    local suffix = following_segment:match("^([^\n]*)") or ""
    local standalone = prefix:match("^%s*$") and suffix:match("^%s*$")

    local placeholder = placeholder_prefix .. counter .. "__"
    local inserted = standalone and ("# " .. placeholder) or placeholder

    replacements[placeholder] = original
    table.insert(sanitized_parts, inserted)

    idx = end_pos + 2
  end

  return table.concat(sanitized_parts), replacements
end

--- Restore Go template markers from placeholders.
---@param text string
---@param replacements table<string, string>
---@return string
function M.unmask_template(text, replacements)
  if not replacements or vim.tbl_isempty(replacements) then
    return text
  end

  for placeholder, original in pairs(replacements) do
    text = text:gsub(vim.pesc("# " .. placeholder), original)
    text = text:gsub(vim.pesc(placeholder), original)
  end
  return text
end

--- Prepare buffer lines for external tools by masking template markers.
---@param lines string[]
---@param bufnr? integer
---@return { text: string, replacements: table<string,string>, had_eol: boolean, original_lines: string[] }
function M.prepare_format_input(lines, bufnr)
  bufnr = bufnr or 0
  local original_lines = vim.list_extend({}, lines)
  local send_lines = vim.list_extend({}, lines)

  local ok, had_eol = pcall(function()
    return vim.bo[bufnr].eol
  end)
  had_eol = ok and had_eol or false

  if had_eol then
    table.insert(send_lines, "")
  end

  local text = table.concat(send_lines, "\n")
  local sanitized, replacements = M.mask_template(text)

  return {
    text = sanitized,
    replacements = replacements,
    had_eol = had_eol,
    original_lines = original_lines,
  }
end

--- Restore formatter output back to template form.
---@param output string
---@param context { replacements: table<string,string>, had_eol: boolean, original_lines: string[] }
---@return string[]
function M.restore_formatted_text(output, context)
  context = context or {}
  local replacements = context.replacements or {}
  local had_eol = context.had_eol or false
  local original_lines = context.original_lines or {}

  local restored = M.unmask_template(output or "", replacements)
  local new_lines = vim.split(restored, "\r?\n", { plain = false, trimempty = false })

  if had_eol and new_lines[#new_lines] == "" then
    table.remove(new_lines)
  end

  if not had_eol and new_lines[#new_lines] == "" and (original_lines[#original_lines] or "") ~= "" then
    table.remove(new_lines)
  end

  if #new_lines == 0 then
    new_lines = { "" }
  end

  return new_lines
end

M.has_template_syntax = has_template_syntax

return M
