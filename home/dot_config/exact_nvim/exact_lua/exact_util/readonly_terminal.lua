local M = {}

--- Close all terminal buffers
function M.close_all_terminals()
  for _, buf in ipairs(vim.api.nvim_list_bufs()) do
    if vim.bo[buf].buftype == "terminal" then
      vim.fn.jobstop(vim.bo[buf].channel)
      vim.cmd("silent! bdelete! " .. buf)
    end
  end
end

--- Run a command in a vertical split terminal
---@param cmd string The command to run
---@param opts? table Options (cwd, etc.)
function M.run_in_split(cmd, opts)
  opts = opts or {}

  -- Close existing terminals first (following jest-runner pattern)
  M.close_all_terminals()

  local original_win = vim.api.nvim_get_current_win()

  vim.cmd("vsplit")
  vim.cmd("enew")
  local term_win = vim.api.nvim_get_current_win()
  local term_buf = vim.api.nvim_get_current_buf()

  local term_opts = {}
  if opts.cwd and opts.cwd ~= "" then
    term_opts.cwd = opts.cwd
  end

  if next(term_opts) == nil then
    term_opts = vim.empty_dict()
  end

  -- Setup close keymap
  vim.keymap.set("n", "q", function()
    if vim.api.nvim_buf_is_valid(term_buf) then
      vim.fn.jobstop(vim.bo[term_buf].channel)
      vim.cmd("silent! bdelete! " .. term_buf)
    end
  end, { noremap = true, silent = true, buffer = term_buf })

  local ok, job_id = pcall(vim.fn.termopen, cmd, term_opts)
  if not ok or job_id <= 0 then
    vim.api.nvim_set_current_win(original_win)
    pcall(vim.api.nvim_win_close, term_win, true)
    local err = not ok and job_id or "termopen failed to start job"
    vim.notify("Failed to run command: " .. tostring(err), vim.log.levels.ERROR)
    return false
  end

  -- Scroll to bottom and ensure insert mode is stopped (so we are in normal mode)
  vim.api.nvim_set_current_win(term_win)
  vim.cmd("normal! G")
  vim.cmd("stopinsert") -- Ensure normal mode

  -- Return focus to original window if requested, otherwise stay in terminal
  if opts.focus_original then
    vim.api.nvim_set_current_win(original_win)
  end

  return true
end

return M
