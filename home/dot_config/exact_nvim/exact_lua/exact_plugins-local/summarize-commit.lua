local M = {
  prompt = [[
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

  ]],
}

-- Utility function to get the staged git diff
local function get_staged_diff()
  local diff = vim.fn.system("git diff --cached")
  if vim.v.shell_error ~= 0 then
    vim.notify("Failed to get git diff", vim.log.levels.ERROR)
    return nil
  end
  return diff
end

-- Utility function to insert output at the cursor position
local function insert_at_cursor(output)
  local win = vim.api.nvim_get_current_win()
  local cursor = vim.api.nvim_win_get_cursor(win)
  vim.api.nvim_buf_set_lines(0, cursor[1] - 1, cursor[1] - 1, false, output)
  vim.api.nvim_win_set_cursor(win, { cursor[1] + #output, cursor[2] })
end

-- Function to generate commit summary using chatblade
local function generate_with_chatblade(prompt, diff)
  -- Escape the prompt and diff properly for shell
  local escaped_prompt = vim.fn.shellescape(prompt)
  local escaped_diff = vim.fn.shellescape(diff)

  -- Construct and execute command
  local command = ("echo %s | chatblade -c 4o -e %s"):format(escaped_prompt, escaped_diff)
  local output = vim.fn.systemlist(command)

  if vim.v.shell_error ~= 0 then
    vim.notify("Failed to generate summary", vim.log.levels.ERROR)
    print(vim.inspect(output))
    return nil
  end

  return output
end

-- Function to generate commit summary using Ollama
local function generate_with_ollama(prompt, diff)
  -- Prepare input with prompt and diff
  local input_with_diff = prompt .. "\n" .. diff
  local json_payload = vim.json.encode({ model = "qwen2.5-coder:32b", prompt = input_with_diff, stream = false })

  -- Construct and execute command
  local command =
    string.format("curl -s -X POST http://localhost:11434/api/generate -d %s", vim.fn.shellescape(json_payload))
  local output = vim.fn.systemlist(command)

  if vim.v.shell_error ~= 0 then
    vim.notify("Failed to generate summary", vim.log.levels.ERROR)
    print(vim.inspect(output))
    return nil
  end

  -- Parse the JSON response
  local response = vim.fn.json_decode(table.concat(output, "\n"))
  if response and response.response then
    return vim.split(response.response, "\n")
  else
    vim.notify("Invalid response format", vim.log.levels.ERROR)
    return nil
  end
end

-- Function to generate commit summary using Cloudflare Workers AI
local function generate_with_cloudflare(prompt, diff)
  -- Build the payload as a Lua table
  local payload = {
    messages = {
      {
        role = "system",
        content = "You are a conventional commits summarizer. You take in git diff data and only respond with a concise but not lacking distinguishing details commit message and bullet-listed commit body in the format of conventional commits.",
      },
      {
        role = "user",
        content = diff,
      },
    },
    max_tokens = 2048,
    stream = false,
  }

  -- Encode the payload to JSON
  local payload_json = vim.json.encode(payload)

  -- Write the JSON payload to a temporary file
  local tmpfile = os.tmpname()
  local f = io.open(tmpfile, "w")
  if f then
    f:write(payload_json)
    f:close()
  else
    vim.notify("Failed to write temp file", vim.log.levels.ERROR)
    return nil
  end

  -- Build the curl command, using the temporary file for the data
  local command = string.format(
    'curl -s -X POST "https://api.cloudflare.com/client/v4/accounts/%s/ai/run/@cf/meta/llama-3.3-70b-instruct-fp8-fast" -H "Authorization: Bearer %s" -H "Content-Type: application/json" -d @%s',
    os.getenv("CLOUDFLARE_WORKERS_AI_ACCOUNT_ID"),
    os.getenv("CLOUDFLARE_WORKERS_AI_API_KEY"),
    tmpfile
  )

  -- Execute the command
  local output = vim.fn.systemlist(command)

  -- Remove the temporary file
  os.remove(tmpfile)

  if vim.v.shell_error ~= 0 then
    vim.notify("Failed to generate summary", vim.log.levels.ERROR)
    print(vim.inspect(output))
    return nil
  end

  -- Parse the JSON response
  local response = vim.json.decode(table.concat(output, "\n"))
  if response and response.result and response.result.response then
    return vim.split(response.result.response, "\n")
  else
    vim.notify("Invalid response format", vim.log.levels.ERROR)
    return nil
  end
end

-- Summarize commit using chatblade
M.summarize_commit = function()
  local diff = get_staged_diff()
  if not diff then
    return
  end

  local output = generate_with_chatblade(M.prompt, diff)
  if output then
    insert_at_cursor(output)
  end
end

-- Summarize commit using Ollama
M.summarize_commit_ollama = function()
  local diff = get_staged_diff()
  if not diff then
    return
  end

  local output = generate_with_ollama(M.prompt, diff)
  if output then
    insert_at_cursor(output)
  end
end

-- Summarize commit using Cloudflare Workers AI
M.summarize_commit_cf = function()
  local diff = get_staged_diff()
  if not diff then
    return
  end

  local output = generate_with_cloudflare(M.prompt, diff)
  if output then
    insert_at_cursor(output)
  end
end

return M
