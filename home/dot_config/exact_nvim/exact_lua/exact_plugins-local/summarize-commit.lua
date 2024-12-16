local M = {
  prompt = [[
    Give me commit message summary from git diff output below using following format:


    Example:

    feat: add new feature

    - Add new feature...
    - Fix bug...
    - Refactor code...

    --------

    Only respond with the commit text and nothing more.

    --------

    Git diff output:

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
  local diff_command = "git diff --cached"
  local diff_output = vim.fn.systemlist(diff_command)

  -- Handle potential empty diff output
  if #diff_output == 0 then
    vim.notify("No changes to commit.", vim.log.levels.WARN, {})
    return
  end

  local input_with_diff = table.concat(diff_output, "\n") .. "\n" .. M.prompt
  local json_payload = vim.json.encode({ model = "llama3.3", prompt = input_with_diff, stream = false })

  local curl_command = "curl -s -X POST http://localhost:11434/api/generate -d " .. vim.fn.shellescape(json_payload)
  local jq_command = "jq -r '.response'"
  local command = curl_command .. " | " .. jq_command

  local output = vim.fn.system(command)

  if output == nil or output == "" then
    vim.notify("Ollama returned an empty response.", vim.log.levels.WARN, {})
    return
  end

  local win = vim.api.nvim_get_current_win()
  local cursor = vim.api.nvim_win_get_cursor(win)

  local split_output = vim.split(output, "\n")

  for _, line in ipairs(split_output) do
    vim.api.nvim_buf_set_lines(0, cursor[1] - 1, cursor[1] - 1, false, { line })
    cursor[1] = cursor[1] + 1
  end
end

return M
