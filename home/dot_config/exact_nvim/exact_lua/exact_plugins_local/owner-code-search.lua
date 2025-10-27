local util = require("util")
local ocs = require("plugins_local_src.owner-code-search")

-- Setup the plugin with any custom config
ocs.setup()

-- Create user commands with proper argument handling
vim.api.nvim_create_user_command("OwnerCodeGrep", function(opts)
  local args = vim.split(opts.args, " ", { trimempty = true })
  if #args < 2 then
    vim.notify("Usage: OwnerCodeGrep <team> <search-pattern>", vim.log.levels.ERROR)
    return
  end
  local team = args[1]
  local pattern = table.concat(args, " ", 2)
  ocs.owner_code_grep(team, pattern)
end, {
  nargs = "+",
  desc = "Grep paths from CODEOWNERS with ripgrep",
})

vim.api.nvim_create_user_command("OwnerCodeGrepPattern", function(opts)
  local args = vim.split(opts.args, " ", { trimempty = true })
  if #args < 2 then
    vim.notify("Usage: OwnerCodeGrepPattern <owner-regex> <search-pattern>", vim.log.levels.ERROR)
    return
  end
  local owner_regex = args[1]
  local pattern = table.concat(args, " ", 2)
  ocs.owner_code_grep_pattern(owner_regex, pattern)
end, {
  nargs = "+",
  desc = "Grep path patterns from CODEOWNERS with ripgrep",
})

vim.api.nvim_create_user_command("OwnerCodeFd", function(opts)
  local args = vim.split(opts.args, " ", { trimempty = true })
  if #args < 2 then
    vim.notify("Usage: OwnerCodeFd <team> <file-pattern>", vim.log.levels.ERROR)
    return
  end
  local team = args[1]
  local pattern = table.concat(args, " ", 2)
  ocs.owner_code_fd(team, pattern)
end, {
  nargs = "+",
  desc = "Find paths from CODEOWNERS with fd",
})

vim.api.nvim_create_user_command("OwnerCodeFdPattern", function(opts)
  local args = vim.split(opts.args, " ", { trimempty = true })
  if #args < 2 then
    vim.notify("Usage: OwnerCodeFdPattern <owner-regex> <file-pattern>", vim.log.levels.ERROR)
    return
  end
  local owner_regex = args[1]
  local pattern = table.concat(args, " ", 2)
  ocs.owner_code_fd_pattern(owner_regex, pattern)
end, {
  nargs = "+",
  desc = "Find path patterns from CODEOWNERS with fd",
})

vim.api.nvim_create_user_command("ListOwners", function()
  ocs.list_owners()
end, {
  desc = "List CODEOWNERS",
})

vim.api.nvim_create_user_command("ClearCodeownersCache", function()
  ocs.clear_cache()
end, {
  desc = "Clear CODEOWNERS cache",
})
return {
  dir = util.get_plugin_src_dir(),
  name = "owner-code-search",
  keys = {
    {
      "<leader>rg",
      function()
        local ok, team = pcall(vim.fn.input, "Team: ")
        if not ok or team == "" then
          return
        end
        local ok2, pattern = pcall(vim.fn.input, "Pattern: ")
        if not ok2 or pattern == "" then
          return
        end
        ocs.owner_code_grep(team, pattern)
      end,
      desc = "Owner Code Grep Search",
    },
    {
      "<leader>rG",
      function()
        local ok, team = pcall(vim.fn.input, "Owner Regex: ")
        if not ok or team == "" then
          return
        end
        local ok2, pattern = pcall(vim.fn.input, "Pattern: ")
        if not ok2 or pattern == "" then
          return
        end
        ocs.owner_code_grep_pattern(team, pattern)
      end,
      desc = "Owner Code Grep Search Pattern",
    },
    {
      "<leader>fd",
      function()
        local ok, team = pcall(vim.fn.input, "Team: ")
        if not ok or team == "" then
          return
        end
        local ok2, pattern = pcall(vim.fn.input, "File Pattern: ")
        if not ok2 or pattern == "" then
          return
        end
        ocs.owner_code_fd(team, pattern)
      end,
      desc = "Owner Code Fd Search",
    },
    {
      "<leader>fD",
      function()
        local ok, team = pcall(vim.fn.input, "Owner Regex: ")
        if not ok or team == "" then
          return
        end
        local ok2, pattern = pcall(vim.fn.input, "File Pattern: ")
        if not ok2 or pattern == "" then
          return
        end
        ocs.owner_code_fd_pattern(team, pattern)
      end,
      desc = "Owner Code Fd Search Pattern",
    },
    {
      "<leader>lo",
      function()
        ocs.list_owners()
      end,
      desc = "List CODEOWNERS",
    },
    {
      "<leader>oc",
      function()
        ocs.clear_cache()
      end,
      desc = "Clear CODEOWNERS cache",
    },
  },
  cmd = {
    "OwnerCodeGrep",
    "OwnerCodeGrepPattern",
    "OwnerCodeFd",
    "OwnerCodeFdPattern",
    "ListOwners",
    "ClearCodeownersCache",
  },
}
