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

M.summarize_commit = function()
  -- Escape the prompt properly for shell
  local escaped_prompt = vim.fn.shellescape(M.prompt)

  -- Get the staged diff
  local diff = vim.fn.system("git diff --cached")
  if vim.v.shell_error ~= 0 then
    vim.notify("Failed to get git diff", vim.log.levels.ERROR)
    return
  end

  -- Escape the diff content
  local escaped_diff = vim.fn.shellescape(diff)

  -- Construct and execute command
  local command = string.format("echo %s | chatblade -c 4o -e %s", escaped_prompt, escaped_diff)
  local output = vim.fn.systemlist(command)

  if vim.v.shell_error ~= 0 then
    vim.notify("Failed to generate summary", vim.log.levels.ERROR)
    return
  end

  -- Insert output at cursor
  local win = vim.api.nvim_get_current_win()
  local cursor = vim.api.nvim_win_get_cursor(win)

  vim.api.nvim_buf_set_lines(0, cursor[1] - 1, cursor[1] - 1, false, output)
  vim.api.nvim_win_set_cursor(win, { cursor[1] + #output, cursor[2] })
end

M.summarize_commit_ollama = function()
  -- Get the staged diff
  local diff = vim.fn.system("git diff --cached")
  if vim.v.shell_error ~= 0 then
    vim.notify("Failed to get git diff", vim.log.levels.ERROR)
    return
  end

  -- Prepare input with prompt and diff
  local input_with_diff = M.prompt .. "\n" .. diff -- Changed order here
  local json_payload = vim.json.encode({ model = "llama3.3", prompt = input_with_diff, stream = false })

  -- Construct and execute command
  local command = string.format(
    "curl -s -X POST http://localhost:11434/api/generate -d %s | jq -r '.response'",
    vim.fn.shellescape(json_payload)
  )
  local output = vim.fn.systemlist(command)

  if vim.v.shell_error ~= 0 then
    vim.notify("Failed to generate summary", vim.log.levels.ERROR)
    return
  end

  -- Insert output at cursor
  local win = vim.api.nvim_get_current_win()
  local cursor = vim.api.nvim_win_get_cursor(win)

  vim.api.nvim_buf_set_lines(0, cursor[1] - 1, cursor[1] - 1, false, output)
  vim.api.nvim_win_set_cursor(win, { cursor[1] + #output, cursor[2] })
end

return M
