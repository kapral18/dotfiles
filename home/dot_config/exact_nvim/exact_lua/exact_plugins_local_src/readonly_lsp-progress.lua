local M = {}

local group = vim.api.nvim_create_augroup("k18_lsp_progress", { clear = true })
local progress_state = {}
local spinner_frames = { "⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷" }
local spinner_index = 1
local progress_timer = nil

local function progress_is_empty()
  for _, tokens in pairs(progress_state) do
    if next(tokens) then
      return false
    end
  end
  return true
end

local function progress_has_active_tokens()
  for _, tokens in pairs(progress_state) do
    for _, value in pairs(tokens) do
      if not value.done then
        return true
      end
    end
  end
  return false
end

local function progress_counts(tokens)
  local done = 0
  local total = 0
  for _, value in pairs(tokens) do
    total = total + 1
    if value.done then
      done = done + 1
    end
  end
  return done, total
end

local function statusline_escape(text)
  local escaped = text:gsub("%%", "%%%%")
  return escaped
end

local function refresh_lualine()
  local ok, lualine = pcall(require, "lualine")
  if ok then
    lualine.refresh()
  end
end

local function stop_progress_timer()
  if progress_timer then
    progress_timer:stop()
    progress_timer:close()
    progress_timer = nil
  end
end

local function start_progress_timer()
  if progress_timer then
    return
  end

  progress_timer = vim.uv.new_timer()
  if not progress_timer then
    return
  end

  progress_timer:start(
    200,
    200,
    vim.schedule_wrap(function()
      if progress_is_empty() then
        stop_progress_timer()
        return
      end

      spinner_index = spinner_index % #spinner_frames + 1
      refresh_lualine()
    end)
  )
end

local function clear_completed_token(client_id, token)
  if not (progress_state[client_id] and progress_state[client_id][token] and progress_state[client_id][token].done) then
    return
  end

  progress_state[client_id][token] = nil
  if not next(progress_state[client_id]) then
    progress_state[client_id] = nil
  end
  if not progress_has_active_tokens() then
    stop_progress_timer()
  end
  refresh_lualine()
end

function M.format()
  local items = {}
  for client_id, tokens in pairs(progress_state) do
    local client = vim.lsp.get_client_by_id(client_id)
    local client_name = client and client.name or ("client#" .. client_id)
    for _, value in pairs(tokens) do
      local parts = {}
      if type(value.title) == "string" and value.title ~= "" then
        table.insert(parts, statusline_escape(value.title))
      end
      if type(value.message) == "string" and value.message ~= "" then
        table.insert(parts, statusline_escape(value.message))
      end

      local done, total = progress_counts(tokens)
      if type(value.percentage) == "number" then
        table.insert(parts, string.format("(%d%%%%)", math.floor(value.percentage + 0.5)))
      end
      table.insert(parts, string.format("(%d/%d)", done, total))
      if value.done then
        table.insert(parts, "- done")
      end

      if #parts > 0 then
        local spinner = value.done and "" or (spinner_frames[spinner_index] .. " ")
        table.insert(items, "[" .. statusline_escape(client_name) .. "] " .. spinner .. table.concat(parts, " "))
      end
    end
  end
  return table.concat(items, ", ")
end

function M.has_progress()
  return M.format() ~= ""
end

function M.lualine_component()
  return {
    function()
      return M.format()
    end,
    cond = M.has_progress,
  }
end

function M.setup()
  vim.api.nvim_create_autocmd("LspProgress", {
    group = group,
    callback = function(ev)
      local data = ev.data or {}
      local client_id = data.client_id
      local params = data.params or {}
      local token = params.token
      local value = params.value
      if not client_id or token == nil or type(value) ~= "table" or not value.kind then
        return
      end

      progress_state[client_id] = progress_state[client_id] or {}
      if value.kind == "end" then
        progress_state[client_id][token] = vim.tbl_extend("force", progress_state[client_id][token] or {}, value, {
          done = true,
        })
        vim.defer_fn(function()
          clear_completed_token(client_id, token)
        end, 700)
      else
        progress_state[client_id][token] = vim.tbl_extend("force", progress_state[client_id][token] or {}, value, {
          done = false,
        })
        start_progress_timer()
      end

      if not progress_has_active_tokens() then
        stop_progress_timer()
      end
      refresh_lualine()
    end,
  })

  vim.api.nvim_create_autocmd("LspDetach", {
    group = group,
    callback = function(ev)
      local client_id = ev.data and ev.data.client_id
      if client_id and progress_state[client_id] then
        progress_state[client_id] = nil
        if progress_is_empty() then
          stop_progress_timer()
        end
        refresh_lualine()
      end
    end,
  })

  vim.api.nvim_create_autocmd("VimLeavePre", {
    group = group,
    callback = stop_progress_timer,
  })
end

return M
