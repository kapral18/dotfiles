local M = {}
local terminals = {}

local function close_terminal(terminal)
  if not terminal then
    return
  end
  if terminals[terminal.owner] == terminal then
    terminals[terminal.owner] = nil
  end
  if vim.api.nvim_buf_is_valid(terminal.buf) and vim.bo[terminal.buf].channel == terminal.job then
    vim.fn.jobstop(terminal.job)
    vim.api.nvim_buf_delete(terminal.buf, { force = true })
  end
end

function M.close(owner)
  close_terminal(terminals[owner])
end

function M.run_in_split(cmd, opts)
  opts = opts or {}
  local owner = assert(opts.owner, "terminal owner is required")
  local previous = terminals[owner]
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

  local ok, job_id = pcall(vim.fn.termopen, cmd, term_opts)
  if not ok or job_id <= 0 then
    vim.api.nvim_set_current_win(original_win)
    pcall(vim.api.nvim_win_close, term_win, true)
    if vim.api.nvim_buf_is_valid(term_buf) then
      vim.api.nvim_buf_delete(term_buf, { force = true })
    end
    local err = not ok and job_id or "termopen failed to start job"
    vim.notify("Failed to run command: " .. tostring(err), vim.log.levels.ERROR)
    return false
  end

  local terminal = { owner = owner, buf = term_buf, job = job_id }
  close_terminal(previous)
  terminals[owner] = terminal
  vim.keymap.set("n", "q", function()
    close_terminal(terminal)
  end, { noremap = true, silent = true, buffer = term_buf })

  vim.api.nvim_create_autocmd("BufWipeout", {
    buffer = term_buf,
    once = true,
    callback = function()
      if terminals[owner] == terminal then
        terminals[owner] = nil
      end
    end,
  })
  if opts.close_on_exit then
    vim.api.nvim_create_autocmd("TermClose", {
      buffer = term_buf,
      once = true,
      callback = function()
        vim.schedule(function()
          close_terminal(terminal)
        end)
      end,
    })
  end

  vim.api.nvim_set_current_win(term_win)
  vim.cmd("normal! G")
  vim.cmd("stopinsert")
  if opts.focus_original then
    vim.api.nvim_set_current_win(original_win)
  end
  return true
end

return M
