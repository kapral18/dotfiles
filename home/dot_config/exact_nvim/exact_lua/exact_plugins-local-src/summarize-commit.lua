local M = {}

-- ───────────────────────────────── SYSTEM CONSTANTS ────────────────────────────
local PROMPT = [[
Read my instruction and follow it carefully.
<<INSTRUCTION START>>
Generate a commit summary using conventional commit format from
the output of a git diff that starts after the word <<DIFF START>>
--------
Only respond with the generated commit text.
--------
Example commit message:
feat: add new feature
- Add new feature
- Update documentation
- Fix bug in existing feature
...
--------
<<INSTRUCTION END>>
<<DIFF START>>
]]

local SYSTEM_MESSAGE = "You are a conventional commits summarizer. You take in git diff"
  .. " data and only respond with a concise yet detailed commit subject"
  .. " plus bullet-listed body. Output nothing else."

-- ───────────────────────────── HELPERS (provider-agnostic) ─────────────────────
local function run(cmd)
  local out = vim.fn.systemlist(cmd)
  if vim.v.shell_error ~= 0 then
    return nil, out
  end
  return out, nil
end

local function write_tmp_json(tbl)
  local path = os.tmpname()
  local f = io.open(path, "w")
  if not f then
    return nil
  end
  f:write(vim.json.encode(tbl))
  f:close()
  return path
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

local function build_curl_file(url, headers, payload_file)
  local h = ""
  for _, hdr in ipairs(headers or {}) do
    h = h .. ' -H "' .. hdr .. '"'
  end
  return ('curl -s -X POST "%s"%s -d @%s'):format(url, h, payload_file)
end

local function decode_and_extract(lines, path)
  local ok, parsed = pcall(vim.fn.json_decode, table.concat(lines or {}, "\n"))
  if not ok or not parsed then
    return nil
  end
  return json_at_path(parsed, path)
end

-- ───────────────────────────────── PROVIDER CONFIG ─────────────────────────────
local providers = {
  -- Ollama local
  ollama = {
    url = "http://localhost:11434/api/generate",
    headers = { "Content-Type: application/json" },
    payload = function(diff)
      return {
        model = "deepseek-r1",
        system = SYSTEM_MESSAGE,
        prompt = PROMPT .. diff,
        think = true,
        stream = false,
      }
    end,
    extract_path = { "response" }, -- string with the whole message
  },

  -- Cloudflare Workers AI
  cloudflare = {
    url = ("https://api.cloudflare.com/client/v4/accounts/%s/ai/run/@cf/qwen/qwen2.5-coder-32b-instruct"):format(
      os.getenv("CLOUDFLARE_WORKERS_AI_ACCOUNT_ID") or ""
    ),
    headers = {
      "Authorization: Bearer " .. (os.getenv("CLOUDFLARE_WORKERS_AI_API_KEY") or ""),
      "Content-Type: application/json",
    },
    payload = function(diff)
      return {
        messages = {
          { role = "system", content = SYSTEM_MESSAGE },
          { role = "user", content = PROMPT .. diff },
        },
        max_tokens = 2048,
        stream = false,
      }
    end,
    extract_path = { "result", "response" }, -- plain text string
  },

  -- OpenRouter (OpenAI-compatible Chat Completions)
  openrouter = {
    url = "https://openrouter.ai/api/v1/chat/completions", -- POST body uses OpenAI chat schema
    headers = {
      "Authorization: Bearer " .. (os.getenv("OPENROUTER_API_KEY") or ""),
      "Content-Type: application/json",
      -- Optional attribution headers per docs (safe to keep; remove if undesired)
      "HTTP-Referer: https://neovim.org",
      "X-Title: Neovim Commit Summarizer",
    },
    payload = function(diff)
      return {
        model = (os.getenv("OPENROUTER_MODEL") or "google/gemini-2.5-flash"),
        messages = {
          { role = "system", content = SYSTEM_MESSAGE },
          { role = "user", content = PROMPT .. diff },
        },
        max_tokens = 2048,
        stream = false,
      }
    end,
    -- Non-streaming: choices.message.content (Lua index 1)
    extract_path = { "choices", 1, "message", "content" },
  },
}

-- ───────────────────────────── GENERIC WORKFLOW ───────────────────────────────
local function summarize_with(provider_key)
  local cfg = providers[provider_key]
  if not cfg then
    vim.notify("Unknown provider: " .. tostring(provider_key), vim.log.levels.ERROR)
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

  local cmd = build_curl_file(cfg.url, cfg.headers, payload_file)
  local out, err = run(cmd)
  os.remove(payload_file)

  if not out then
    vim.notify("Failed to generate summary", vim.log.levels.ERROR)
    if err then
      print(vim.inspect(err))
    end
    return
  end

  local text = decode_and_extract(out, cfg.extract_path)
  if type(text) ~= "string" or text == "" then
    vim.notify("Invalid response format from " .. provider_key, vim.log.levels.ERROR)
    return
  end

  insert_at_cursor(vim.split(text, "\n"))
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
