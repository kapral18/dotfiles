--- Markdown / MDX window options (wrap + linebreak) for core autocmds.
local M = {}

---@param ft string
---@return boolean
function M.is_markdown_family_ft(ft)
  return ft == "markdown"
    or ft == "mdx"
    or ft == "rmarkdown"
    or vim.startswith(ft, "markdown.")
    or vim.startswith(ft, "mdx.")
end

---@param bufnr integer
function M.soft_wrap_buffer_wins(bufnr)
  if not bufnr or not vim.api.nvim_buf_is_valid(bufnr) then
    return
  end
  if not M.is_markdown_family_ft(vim.bo[bufnr].filetype) then
    return
  end
  for _, win in ipairs(vim.fn.win_findbuf(bufnr)) do
    vim.api.nvim_set_option_value("wrap", true, { win = win })
    vim.api.nvim_set_option_value("linebreak", true, { win = win })
    vim.api.nvim_set_option_value("breakindent", true, { win = win })
  end
end

return M
