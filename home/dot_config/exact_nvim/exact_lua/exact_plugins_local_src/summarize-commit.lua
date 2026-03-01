local M = {}

-- ───────────────────────────────── SYSTEM CONSTANTS ────────────────────────────
local PROMPT = [[
Generate a commit summary using conventional commit format from the output of a git diff.
Only respond with the generated commit text (no reasoning, no explanation).

<<DIFF START>>
]]

local SYSTEM_MESSAGE =
  "You are a conventional commits summarizer. Output only the final commit message text. Do not include reasoning."

-- ───────────────────────────── HELPERS (provider-agnostic) ─────────────────────
local function run(argv_or_cmd)
  local out = vim.fn.systemlist(argv_or_cmd)
  local code = vim.v.shell_error
  if code ~= 0 then
    return nil, out, code
  end
  return out, nil, code
end

local function write_tmp_json(tbl)
  local path = os.tmpname()
  local ok, err = pcall(function()
    local f = assert(io.open(path, "w"))
    f:write(vim.json.encode(tbl))
    f:close()
  end)

  if not ok then
    pcall(os.remove, path)
    return nil
  end
  return path
end

local function read_file_lines(path)
  local ok, lines = pcall(vim.fn.readfile, path)
  if not ok then
    return nil
  end
  return lines
end

local function take_first(lines, n)
  local out = {}
  if type(lines) ~= "table" or n <= 0 then
    return out
  end
  for i = 1, math.min(#lines, n) do
    out[i] = lines[i]
  end
  return out
end

local function insert_at_cursor(lines)
  local row = vim.api.nvim_win_get_cursor(0)[1]
  vim.api.nvim_buf_set_lines(0, row - 1, row - 1, false, lines)
  vim.api.nvim_win_set_cursor(0, { row + #lines, 0 })
end

local function get_staged_diff()
  local out = vim.fn.system("git diff --cached")
  if vim.v.shell_error ~= 0 then
    vim.notify("Failed to get git diff", vim.log.levels.ERROR)
    return nil
  end
  return out
end

local function json_at_path(obj, path)
  local cur = obj
  for _, key in ipairs(path) do
    if type(key) == "number" then
      cur = cur and cur[key]
    else
      cur = cur and cur[key]
    end
    if cur == nil then
      return nil
    end
  end
  return cur
end

local function normalize_text(v)
  if type(v) == "string" then
    return v
  end
  if type(v) ~= "table" then
    return nil
  end

  -- Some OpenAI-like schemas represent content as an array of parts.
  if vim.tbl_islist(v) then
    local parts = {}
    for _, item in ipairs(v) do
      if type(item) == "string" then
        table.insert(parts, item)
      elseif type(item) == "table" then
        if type(item.text) == "string" then
          table.insert(parts, item.text)
        elseif type(item.content) == "string" then
          table.insert(parts, item.content)
        end
      end
    end
    if #parts > 0 then
      return table.concat(parts, "")
    end
  end

  return nil
end

local function curl_post_json(url, headers, payload_file, timeout)
  timeout = timeout or 30

  local body_file = os.tmpname()
  local stderr_file = os.tmpname()
  local argv = {
    "curl",
    "-sS",
    "-X",
    "POST",
    "--max-time",
    tostring(timeout),
    url,
  }

  for _, hdr in ipairs(headers or {}) do
    table.insert(argv, "-H")
    table.insert(argv, hdr)
  end

  table.insert(argv, "--data-binary")
  table.insert(argv, "@" .. payload_file)

  table.insert(argv, "--output")
  table.insert(argv, body_file)

  table.insert(argv, "--stderr")
  table.insert(argv, stderr_file)

  table.insert(argv, "--write-out")
  table.insert(argv, "__CURLMETA__%{http_code}|%{content_type}")

  local meta_lines, cmd_err, exit_code = run(argv)
  local body_lines = read_file_lines(body_file) or {}
  local stderr_lines = read_file_lines(stderr_file) or {}
  pcall(os.remove, body_file)
  pcall(os.remove, stderr_file)

  local meta = meta_lines and table.concat(meta_lines, "\n") or ""
  if meta == "" and type(cmd_err) == "table" then
    meta = table.concat(cmd_err, "\n")
  end
  local status, content_type = meta:match("__CURLMETA__(%d%d%d)|([^\r\n]*)")

  return {
    ok = meta_lines ~= nil,
    cmd_err = cmd_err,
    exit_code = exit_code,
    status = tonumber(status),
    content_type = content_type,
    body_lines = body_lines,
    stderr_lines = stderr_lines,
  }
end

local function decode_json(lines)
  local ok, parsed = pcall(vim.fn.json_decode, table.concat(lines or {}, "\n"))
  if not ok or not parsed then
    return nil
  end
  return parsed
end

local function extract_text_with_fallbacks(parsed, path, fallbacks)
  local text = path and normalize_text(json_at_path(parsed, path)) or nil
  if type(text) == "string" and text ~= "" then
    return text
  end

  for _, p in ipairs(fallbacks or {}) do
    local v = normalize_text(json_at_path(parsed, p))
    if type(v) == "string" and v ~= "" then
      return v
    end
  end

  return nil
end

local function strip_thinking(text)
  if type(text) ~= "string" then
    return text
  end

  -- Common "reasoning" tags some models emit despite instructions.
  text = text:gsub("<think>[%s%S]-</think>", "")
  text = text:gsub("<thinking>[%s%S]-</thinking>", "")
  text = text:gsub("<analysis>[%s%S]-</analysis>", "")

  -- Trim leading/trailing whitespace after stripping.
  text = text:gsub("^%s+", ""):gsub("%s+$", "")
  return text
end

local function env_trim(name)
  local v = os.getenv(name)
  if not v then
    return nil
  end
  v = v:gsub("^%s+", ""):gsub("%s+$", "")
  if v == "" then
    return nil
  end
  return v
end

local function env_bool_or_string(name)
  local v = env_trim(name)
  if not v then
    return nil
  end
  local lower = v:lower()
  if lower == "true" or lower == "1" or lower == "yes" or lower == "on" then
    return true
  end
  if lower == "false" or lower == "0" or lower == "no" or lower == "off" then
    return false
  end
  return v
end

local function env_number(name)
  local v = env_trim(name)
  if not v then
    return nil
  end
  local n = tonumber(v)
  return n
end

local function is_conventional_header(line)
  if type(line) ~= "string" then
    return false
  end
  local l = line:gsub("^%s+", ""):gsub("%s+$", "")
  local typ = l:match("^([%a]+)")
  if not typ then
    return false
  end
  local allowed = {
    feat = true,
    fix = true,
    docs = true,
    style = true,
    refactor = true,
    perf = true,
    test = true,
    build = true,
    ci = true,
    chore = true,
    revert = true,
  }
  if not allowed[typ] then
    return false
  end

  local rest = l:sub(#typ + 1)
  if rest:sub(1, 1) == "(" then
    local scope = rest:match("^(%b())")
    if not scope then
      return false
    end
    rest = rest:sub(#scope + 1)
  end

  if rest:sub(1, 1) == "!" then
    rest = rest:sub(2)
  end

  if rest:sub(1, 1) ~= ":" then
    return false
  end
  local next_ch = rest:sub(2, 2)
  if next_ch ~= " " and next_ch ~= "\t" then
    return false
  end
  return true
end

local function extract_commit_from_reasoning(text)
  if type(text) ~= "string" or text == "" then
    return nil
  end

  local lines = vim.split(text, "\n", { plain = true })
  for i, line in ipairs(lines) do
    local trimmed = line:gsub("^%s+", ""):gsub("%s+$", "")
    if is_conventional_header(trimmed) then
      local out = { trimmed }
      for j = i + 1, #lines do
        local l = lines[j]:gsub("^%s+", ""):gsub("%s+$", "")
        if l == "" then
          if #out > 1 then
            break
          end
        elseif l:match("^[-*+]%s+") then
          table.insert(out, l)
        else
          break
        end
      end
      return table.concat(out, "\n")
    end
  end

  return nil
end

local function require_env(provider_key, vars)
  local missing = {}
  for _, v in ipairs(vars or {}) do
    local val = os.getenv(v)
    if not val or val == "" then
      table.insert(missing, v)
    end
  end
  if #missing > 0 then
    vim.notify(("Missing env for %s: %s"):format(provider_key, table.concat(missing, ", ")), vim.log.levels.ERROR)
    return false
  end
  return true
end

-- ───────────────────────────────── PROVIDER CONFIG ─────────────────────────────
local providers = {
  -- Ollama local
  ollama = {
    url = "http://localhost:11434/api/generate",
    timeout = 60,
    headers = { "Content-Type: application/json" },
    payload = function(diff)
      local think = env_bool_or_string("OLLAMA_THINK")
      if think == nil then
        think = false
      end
      local model = env_trim("OLLAMA_MODEL") or "gemma3"
      local temperature = env_number("OLLAMA_TEMPERATURE")

      local options = nil
      if temperature ~= nil then
        options = { temperature = temperature }
      end
      return {
        model = model,
        system = SYSTEM_MESSAGE,
        prompt = PROMPT .. diff,
        think = think,
        options = options,
        stream = false,
      }
    end,
    extract_path = { "response" }, -- string with the whole message
  },

  -- Cloudflare Workers AI
  cloudflare = {
    required_env = { "CLOUDFLARE_WORKERS_AI_ACCOUNT_ID", "CLOUDFLARE_WORKERS_AI_API_KEY" },
    timeout = 90,
    url = function()
      local account_id = env_trim("CLOUDFLARE_WORKERS_AI_ACCOUNT_ID") or ""
      local model = env_trim("CLOUDFLARE_WORKERS_AI_MODEL") or "@cf/zai-org/glm-4.7-flash"
      return ("https://api.cloudflare.com/client/v4/accounts/%s/ai/run/%s"):format(account_id, model)
    end,
    headers = function()
      return {
        "Authorization: Bearer " .. (os.getenv("CLOUDFLARE_WORKERS_AI_API_KEY") or ""),
        "Content-Type: application/json",
      }
    end,
    payload = function(diff)
      local reasoning_effort = env_trim("CLOUDFLARE_REASONING_EFFORT")
      if reasoning_effort ~= nil then
        local allowed = { low = true, medium = true, high = true }
        if not allowed[reasoning_effort:lower()] then
          reasoning_effort = nil
        end
      end

      local payload = {
        messages = {
          { role = "system", content = SYSTEM_MESSAGE },
          { role = "user", content = PROMPT .. diff },
        },
        max_tokens = 2048,
        temperature = 0,
        stream = false,
      }

      if reasoning_effort ~= nil then
        payload.reasoning_effort = reasoning_effort
      end

      return payload
    end,
    -- Workers AI commonly returns an OpenAI-like Chat Completions object under `result`.
    extract_path = { "result", "choices", 1, "message", "content" },
    extract_fallbacks = {
      { "result" }, -- some models return plain strings
      { "result", "response" }, -- older/non-chat schema
      { "result", "answer" },
      { "result", "text" },
      { "result", "output_text" },
      { "result", "message", "content" },
      { "result", "choices", 1, "message", "content" },
      { "result", "messages", 1, "content" },
    },
  },

  -- OpenRouter (OpenAI-compatible Chat Completions)
  openrouter = {
    url = "https://openrouter.ai/api/v1/chat/completions", -- POST body uses OpenAI chat schema
    required_env = { "OPENROUTER_API_KEY" },
    timeout = 90,
    headers = function()
      return {
        "Authorization: Bearer " .. (os.getenv("OPENROUTER_API_KEY") or ""),
        "Content-Type: application/json",
        -- Optional attribution headers per docs (safe to keep; remove if undesired)
        "HTTP-Referer: https://neovim.org",
        "X-Title: Neovim Commit Summarizer",
      }
    end,
    payload = function(diff)
      local effort = env_trim("OPENROUTER_REASONING_EFFORT") or "none"
      return {
        model = (os.getenv("OPENROUTER_MODEL") or "z-ai/glm-5"),
        messages = {
          { role = "system", content = SYSTEM_MESSAGE },
          { role = "user", content = PROMPT .. diff },
        },
        -- OpenRouter: disable reasoning when the upstream model supports it.
        -- (If unsupported, OpenRouter/provider may ignore it.)
        reasoning = { effort = effort },
        max_tokens = 2048,
        temperature = 0,
        stream = false,
      }
    end,
    -- Non-streaming: choices.message.content (Lua index 1)
    extract_path = { "choices", 1, "message", "content" },
  },
}

local function format_api_errors(parsed)
  local errs = parsed and parsed.errors
  if type(errs) ~= "table" or #errs == 0 then
    return nil
  end

  local parts = {}
  for i, e in ipairs(errs) do
    if i > 3 then
      break
    end
    if type(e) == "table" then
      local prefix = e.code and ("(" .. tostring(e.code) .. ") ") or ""
      table.insert(parts, prefix .. (e.message or vim.inspect(e)))
    else
      table.insert(parts, tostring(e))
    end
  end
  return table.concat(parts, "; ")
end

local function format_generic_error(parsed)
  if type(parsed) ~= "table" then
    return nil
  end

  local err = parsed.error
  if type(err) == "string" and err ~= "" then
    return err
  end
  if type(err) == "table" then
    if type(err.message) == "string" and err.message ~= "" then
      return err.message
    end
    if type(err.error) == "string" and err.error ~= "" then
      return err.error
    end
  end

  if type(parsed.message) == "string" and parsed.message ~= "" then
    return parsed.message
  end
  if type(parsed.detail) == "string" and parsed.detail ~= "" then
    return parsed.detail
  end

  return nil
end

-- ───────────────────────────── GENERIC WORKFLOW ───────────────────────────────
local function summarize_with(provider_key)
  local ok, err = pcall(function()
    local cfg = providers[provider_key]
    if not cfg then
      vim.notify("Unknown provider: " .. tostring(provider_key), vim.log.levels.ERROR)
      return
    end

    if cfg.required_env and not require_env(provider_key, cfg.required_env) then
      return
    end

    local diff = get_staged_diff()
    if not diff or diff == "" then
      vim.notify("No staged changes to summarize", vim.log.levels.WARN)
      return
    end

    local payload_file = write_tmp_json(cfg.payload(diff))
    if not payload_file then
      vim.notify("Failed to write temp JSON payload", vim.log.levels.ERROR)
      return
    end

    local url = type(cfg.url) == "function" and cfg.url() or cfg.url
    local headers = type(cfg.headers) == "function" and cfg.headers() or cfg.headers
    local resp = curl_post_json(url, headers, payload_file, cfg.timeout)
    pcall(os.remove, payload_file)

    local parsed = decode_json(resp.body_lines)
    if not parsed and not resp.ok then
      local msg = ("Failed to generate summary (curl exit %s)"):format(tostring(resp.exit_code or "?"))
      vim.notify(msg, vim.log.levels.ERROR)
      local err_preview = table.concat(take_first(resp.stderr_lines, 10), "\n")
      if err_preview ~= "" then
        print(err_preview)
      elseif resp.cmd_err then
        print(vim.inspect(resp.cmd_err))
      end
      return
    end

    if not parsed then
      local preview = table.concat(take_first(resp.body_lines, 30), "\n")
      vim.notify(
        ("Invalid JSON from %s (HTTP %s, %s). See :messages for body preview."):format(
          provider_key,
          tostring(resp.status or "?"),
          tostring(resp.content_type or "?")
        ),
        vim.log.levels.ERROR
      )
      if preview ~= "" then
        print(preview)
      end
      return
    end

    if resp.status and resp.status >= 400 then
      local msg = format_api_errors(parsed) or format_generic_error(parsed) or "HTTP error"
      vim.notify(("%s HTTP %d: %s"):format(provider_key, resp.status, msg), vim.log.levels.ERROR)
      return
    end

    if parsed.success == false then
      local msg = format_api_errors(parsed) or format_generic_error(parsed) or "Unknown API error"
      vim.notify(
        ("%s API error (HTTP %s): %s"):format(provider_key, tostring(resp.status or "?"), msg),
        vim.log.levels.ERROR
      )
      return
    end

    if parsed.error ~= nil then
      local msg = format_generic_error(parsed) or "Unknown error"
      vim.notify(("%s API error: %s"):format(provider_key, msg), vim.log.levels.ERROR)
      return
    end

    local text = extract_text_with_fallbacks(parsed, cfg.extract_path, cfg.extract_fallbacks)
    if type(text) ~= "string" or text == "" then
      if provider_key == "cloudflare" then
        local reasoning_text =
          normalize_text(json_at_path(parsed, { "result", "choices", 1, "message", "reasoning_content" }))
          or normalize_text(json_at_path(parsed, { "result", "choices", 1, "message", "reasoning" }))
        local extracted = extract_commit_from_reasoning(reasoning_text or "")
        if type(extracted) == "string" and extracted ~= "" then
          insert_at_cursor(vim.split(extracted, "\n"))
          return
        end
      end

      vim.notify(
        ("Invalid response format from %s (HTTP %s). See :messages for parsed.result preview."):format(
          provider_key,
          tostring(resp.status or "?")
        ),
        vim.log.levels.ERROR
      )
      print(vim.inspect(parsed.result))
      return
    end

    text = strip_thinking(text)
    insert_at_cursor(vim.split(text, "\n"))
  end)

  if not ok then
    vim.notify("Error during summarization: " .. tostring(err), vim.log.levels.ERROR)
  end
end

-- ────────────────────────── PUBLIC COMMANDS ───────────────────────────────────
M.summarize_commit_ollama = function()
  summarize_with("ollama")
end
M.summarize_commit_cf = function()
  summarize_with("cloudflare")
end
M.summarize_commit_openrouter = function()
  summarize_with("openrouter")
end

return M
