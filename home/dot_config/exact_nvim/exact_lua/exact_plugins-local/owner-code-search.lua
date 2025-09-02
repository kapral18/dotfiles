local config_path = vim.fn.stdpath("config")

local ocs = require("plugins-local-src.owner-code-search")

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
  dir = config_path .. "/lua/plugins-local-src",
  name = "owner-code-search",
  keys = {
    {
      "<leader>rg",
      function()
        local team = vim.fn.input("Team: ")
        if team == "" then
          return
        end
        local pattern = vim.fn.input("Pattern: ")
        if pattern == "" then
          return
        end
        ocs.owner_code_grep(team, pattern)
      end,
      desc = "Owner Code Grep Search",
    },
    {
      "<leader>rG",
      function()
        local team = vim.fn.input("Owner Regex: ")
        if team == "" then
          return
        end
        local pattern = vim.fn.input("Pattern: ")
        if pattern == "" then
          return
        end
        ocs.owner_code_grep_pattern(team, pattern)
      end,
      desc = "Owner Code Grep Search Pattern",
    },
    {
      "<leader>fd",
      function()
        local team = vim.fn.input("Team: ")
        if team == "" then
          return
        end
        local pattern = vim.fn.input("File Pattern: ")
        if pattern == "" then
          return
        end
        ocs.owner_code_fd(team, pattern)
      end,
      desc = "Owner Code Fd Search",
    },
    {
      "<leader>fD",
      function()
        local team = vim.fn.input("Owner Regex: ")
        if team == "" then
          return
        end
        local pattern = vim.fn.input("File Pattern: ")
        if pattern == "" then
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
