local M = {}

-- ───────────────────────────────── SYSTEM CONSTANTS ────────────────────────────
local PROMPT = [[
Generate a commit summary using conventional commit format from the output of a git diff.
Return only the commit message, in this exact shape:

<type>(<scope optional>): <short summary>

Choose the header type by the most meaningful behavior change, not by the files touched.
When more than one type could apply, prefer this order:

1. feat: new or changed functionality, workflows, runtime behavior, prompts, or tooling behavior
2. fix: corrected broken behavior, regressions, errors, or incorrect output
3. chore/refactor/test/build/ci: maintenance, reshaping, or support work without user-facing behavior changes
4. docs: documentation-only changes; never use docs when the diff also changes functionality, bug behavior, configuration, scripts, prompts, or runtime/tooling behavior

- one bullet for each distinct functional change (intent or behavior), not per file
- use a separate bullet when a single file has multiple functional/intent changes
- avoid bullets that are only file names

Do not add explanations, no prose, no markdown wrappers, no JSON, and no extra text.
]]

local SYSTEM_MESSAGE =
  "You are a conventional commit message specialist. Classify the header by the most meaningful behavior change, not by file paths. Use docs only for documentation-only diffs. Return only valid commit message text in the requested format. Do not include reasoning."

local DEFAULT_MAX_OUTPUT_TOKENS = 2048
local CLOUDFLARE_DEFAULT_MODEL = "@cf/zai-org/glm-5.2"
local GEMINI_DEFAULT_MODEL = "gemini-flash-latest"
local OPENROUTER_DEFAULT_MODEL = "z-ai/glm-5.2"
local OPENROUTER_CONTEXT_COMPRESSION_PLUGIN = { id = "context-compression" }

-- ───────────────────────────── HELPERS (provider-agnostic) ─────────────────────
local function split_lines(text)
  local lines = {}
  if type(text) ~= "string" or text == "" then
    return lines
  end

  for line in vim.gsplit(text, "\n", { plain = true, trimempty = true }) do
    table.insert(lines, line)
  end
  return lines
end

local function run(argv)
  local ok, job_or_err = pcall(vim.system, argv, { text = true })
  if not ok or not job_or_err then
    return {
      ok = false,
      stdout_lines = {},
      stderr_lines = { tostring(job_or_err or "Failed to start command") },
    }
  end

  local result = job_or_err:wait()
  if not result then
    return {
      ok = false,
      stdout_lines = {},
      stderr_lines = { "Command terminated unexpectedly" },
    }
  end

  return {
    ok = result.code == 0,
    stdout_lines = split_lines(result.stdout),
    stderr_lines = split_lines(result.stderr),
    exit_code = result.code,
    signal = result.signal,
  }
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

local function first_nonempty(lines)
  for _, line in ipairs(lines or {}) do
    if type(line) == "string" and line ~= "" then
      return line
    end
  end
  return nil
end

local function truncate(text, max_len)
  if type(text) ~= "string" or #text <= max_len then
    return text
  end
  return text:sub(1, max_len - 3) .. "..."
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

  table.insert(argv, "--write-out")
  table.insert(argv, "__CURLMETA__%{http_code}|%{content_type}")

  local result = run(argv)
  local body_lines = read_file_lines(body_file) or {}
  pcall(os.remove, body_file)

  local meta = table.concat(result.stdout_lines or {}, "\n")
  local status, content_type = meta:match("__CURLMETA__(%d%d%d)|([^\r\n]*)")

  return {
    ok = result.ok,
    exit_code = result.exit_code,
    signal = result.signal,
    status = tonumber(status),
    content_type = content_type,
    body_lines = body_lines,
    stderr_lines = result.stderr_lines or {},
  }
end

local function format_curl_transport_error(resp, timeout)
  local parts = { ("curl exit %s"):format(tostring(resp.exit_code or "?")) }
  if resp.signal and resp.signal ~= 0 then
    table.insert(parts, ("signal %s"):format(tostring(resp.signal)))
  end
  if resp.exit_code == 28 then
    table.insert(parts, ("timed out after %ss"):format(tostring(timeout or "?")))
  end

  local detail = first_nonempty(resp.stderr_lines) or first_nonempty(resp.body_lines)
  if detail then
    table.insert(parts, truncate(detail, 180))
  else
    table.insert(parts, "curl did not return response details")
  end

  return table.concat(parts, ", ")
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

local function normalize_commit_output(text)
  if type(text) ~= "string" then
    return text
  end

  text = text:gsub("\\r\\n", "\n")
  text = text:gsub("\\n", "\n")
  text = strip_thinking(text)

  return text
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

local function is_docs_path(path)
  if type(path) ~= "string" or path == "" then
    return false
  end

  local normalized = path:gsub("\\", "/"):lower()
  local filename = normalized:match("[^/]+$") or normalized
  if normalized:match("^docs?/") or normalized:match("/docs?/") then
    return true
  end
  if normalized:match("^documentation/") or normalized:match("/documentation/") then
    return true
  end
  if normalized:match("^%.mermaids/") then
    return true
  end

  return filename:match("^readme%.") ~= nil
    or filename:match("^changelog%.") ~= nil
    or filename:match("%.mdx?$") ~= nil
    or filename:match("%.rst$") ~= nil
    or filename:match("%.adoc$") ~= nil
end

local function diff_has_non_docs_path(diff)
  local saw_path = false
  for line in vim.gsplit(diff or "", "\n", { plain = true }) do
    local path = line:match("^diff %-%-git a/.- b/(.+)$")
    if path and path ~= "/dev/null" then
      saw_path = true
      if not is_docs_path(path) then
        return true
      end
    end
  end
  return not saw_path
end

local function added_diff_text(diff)
  local added = {}
  for line in vim.gsplit(diff or "", "\n", { plain = true }) do
    if line:sub(1, 1) == "+" and line:sub(1, 3) ~= "+++" then
      table.insert(added, line:sub(2):lower())
    end
  end
  return table.concat(added, "\n")
end

local function fallback_non_docs_type(diff)
  local added = added_diff_text(diff)
  if added:match("functionality") or added:match("feature") or added:match("workflow") or added:match("runtime") then
    return "feat"
  end
  if added:match("behavior") or added:match("tooling") or added:match("prompt") or added:match("support") then
    return "feat"
  end
  if added:match("bug") or added:match("fix") or added:match("regression") or added:match("incorrect") then
    return "fix"
  end
  if added:match("broken") or added:match("error") or added:match("wrong") or added:match("correct") then
    return "fix"
  end
  return "chore"
end

local function force_non_docs_header(text, diff)
  if type(text) ~= "string" or not diff_has_non_docs_path(diff) then
    return text
  end

  local lines = vim.split(text, "\n", { plain = true })
  local header = lines[1]
  if type(header) ~= "string" then
    return text
  end

  local leading = header:match("^(%s*)") or ""
  local trimmed = header:gsub("^%s+", "")
  local rest = trimmed:match("^docs(.*)")
  if not rest or not is_conventional_header(trimmed) then
    return text
  end

  lines[1] = leading .. fallback_non_docs_type(diff) .. rest
  return table.concat(lines, "\n")
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

local function is_kimi_model(model)
  if type(model) ~= "string" then
    return false
  end
  model = model:lower()
  return model:find("kimi", 1, true) ~= nil or model:find("moonshot", 1, true) ~= nil
end

local function openrouter_model_id()
  local model = env_trim("OPENROUTER_MODEL") or OPENROUTER_DEFAULT_MODEL
  local nitro = env_bool_or_string("OPENROUTER_NITRO")
  if nitro == nil then
    nitro = true
  end
  if nitro and is_kimi_model(model) and not model:find(":", 1, true) then
    model = model .. ":nitro"
  end
  return model
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
  -- Cloudflare Workers AI
  cloudflare = {
    required_env = { "CLOUDFLARE_WORKERS_AI_ACCOUNT_ID", "CLOUDFLARE_WORKERS_AI_API_KEY" },
    timeout = 90,
    url = function()
      local account_id = env_trim("CLOUDFLARE_WORKERS_AI_ACCOUNT_ID") or ""
      return ("https://api.cloudflare.com/client/v4/accounts/%s/ai/v1/chat/completions"):format(account_id)
    end,
    headers = function()
      return {
        "Authorization: Bearer " .. (os.getenv("CLOUDFLARE_WORKERS_AI_API_KEY") or ""),
        "Content-Type: application/json",
      }
    end,
    payload = function(diff)
      local thinking = env_bool_or_string("CLOUDFLARE_THINKING")
      if thinking == nil then
        thinking = false
      end

      local reasoning_effort = env_trim("CLOUDFLARE_REASONING_EFFORT")
      if reasoning_effort ~= nil then
        local allowed = { low = true, medium = true, high = true }
        if not allowed[reasoning_effort:lower()] then
          reasoning_effort = nil
        end
      end

      local model = env_trim("CLOUDFLARE_WORKERS_AI_MODEL") or CLOUDFLARE_DEFAULT_MODEL
      local payload = {
        model = model,
        messages = {
          { role = "system", content = SYSTEM_MESSAGE },
          { role = "user", content = diff },
        },
        chat_template_kwargs = {
          thinking = thinking,
        },
        max_tokens = DEFAULT_MAX_OUTPUT_TOKENS,
        temperature = 0,
        stream = false,
      }

      if reasoning_effort ~= nil then
        payload.reasoning_effort = reasoning_effort
      end

      return payload
    end,
    extract_path = { "choices", 1, "message", "content" },
    extract_fallbacks = {
      { "choices", 1, "message", "content" },
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
      local thinking = env_bool_or_string("OPENROUTER_THINKING")
      if thinking == nil then
        thinking = false
      end

      local reasoning
      if thinking then
        local effort = env_trim("OPENROUTER_REASONING_EFFORT") or "low"
        local allowed = {
          xhigh = true,
          high = true,
          medium = true,
          low = true,
          minimal = true,
        }
        if not allowed[effort:lower()] then
          effort = "low"
        end
        reasoning = { effort = effort }
      else
        reasoning = { effort = "none" }
      end

      local model = openrouter_model_id()
      local payload = {
        model = model,
        messages = {
          { role = "system", content = SYSTEM_MESSAGE },
          { role = "user", content = diff },
        },
        reasoning = reasoning,
        plugins = { OPENROUTER_CONTEXT_COMPRESSION_PLUGIN },
        chat_template_kwargs = {
          thinking = thinking,
        },
        max_tokens = DEFAULT_MAX_OUTPUT_TOKENS,
        temperature = 0,
        stream = false,
      }

      return payload
    end,
    -- Non-streaming: choices.message.content (Lua index 1)
    extract_path = { "choices", 1, "message", "content" },
  },

  -- Gemini API
  gemini = {
    url = function()
      local base = "https://generativelanguage.googleapis.com"
      local model = env_trim("GEMINI_MODEL") or GEMINI_DEFAULT_MODEL
      return ("%s/v1beta/models/%s:generateContent?key=%s"):format(base, model, os.getenv("GEMINI_API_KEY") or "")
    end,
    required_env = { "GEMINI_API_KEY" },
    timeout = 90,
    headers = { "Content-Type: application/json" },
    payload = function(diff)
      local max_output_tokens = env_number("GEMINI_MAX_OUTPUT_TOKENS") or DEFAULT_MAX_OUTPUT_TOKENS

      return {
        systemInstruction = {
          parts = {
            { text = SYSTEM_MESSAGE },
          },
        },
        contents = {
          {
            parts = {
              { text = diff },
            },
          },
        },
        generationConfig = {
          temperature = 0,
          maxOutputTokens = max_output_tokens,
        },
      }
    end,
    -- Gemini response structure: candidates[0].content.parts[0].text
    extract_path = { "candidates", 1, "content", "parts", 1, "text" },
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

    local request = PROMPT .. "\n\n<<DIFF START>>\n" .. diff

    local payload_file = write_tmp_json(cfg.payload(request))
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
      local msg = ("Failed to generate summary with %s (%s)"):format(
        provider_key,
        format_curl_transport_error(resp, cfg.timeout)
      )
      vim.notify(msg, vim.log.levels.ERROR)
      local err_preview = table.concat(take_first(resp.stderr_lines, 10), "\n")
      if err_preview ~= "" then
        print(err_preview)
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
      local reasoning_text
      if provider_key == "cloudflare" then
        reasoning_text = normalize_text(json_at_path(parsed, { "choices", 1, "message", "reasoning_content" }))
          or normalize_text(json_at_path(parsed, { "choices", 1, "message", "reasoning" }))
          or normalize_text(json_at_path(parsed, { "result", "choices", 1, "message", "reasoning_content" }))
          or normalize_text(json_at_path(parsed, { "result", "choices", 1, "message", "reasoning" }))
      elseif provider_key == "openrouter" then
        reasoning_text = normalize_text(json_at_path(parsed, { "choices", 1, "message", "reasoning" }))
          or normalize_text(json_at_path(parsed, { "choices", 1, "message", "reasoning_content" }))
      end
      if reasoning_text then
        local extracted = extract_commit_from_reasoning(reasoning_text)
        if type(extracted) == "string" and extracted ~= "" then
          extracted = force_non_docs_header(normalize_commit_output(extracted), diff)
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

    text = normalize_commit_output(text)
    text = force_non_docs_header(text, diff)

    insert_at_cursor(vim.split(text, "\n"))
  end)

  if not ok then
    vim.notify("Error during summarization: " .. tostring(err), vim.log.levels.ERROR)
  end
end

-- ────────────────────────── PUBLIC COMMANDS ───────────────────────────────────
M.summarize_commit_cf = function()
  summarize_with("cloudflare")
end
M.summarize_commit_openrouter = function()
  summarize_with("openrouter")
end
M.summarize_commit_gemini = function()
  summarize_with("gemini")
end

return M
