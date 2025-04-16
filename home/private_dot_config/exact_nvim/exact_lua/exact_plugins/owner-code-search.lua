local config_path = vim.fn.stdpath("config")

return {
  dir = config_path .. "/lua/plugins-local",
  keys = {
    {
      "<leader>rg",
      function()
        local team = vim.fn.input("Team: ")
        local pattern = vim.fn.input("Pattern: ")

        if not team or not pattern then
          vim.notify("Usage: OwnerCodeGrep <team> <search-pattern>", vim.log.levels.ERROR)
          return
        end

        require("plugins-local.owner-code-search").owner_code_grep(team, pattern)
      end,
      desc = "Owner Code Grep Search",
    },
    {
      "<leader>rG",
      function()
        local team = vim.fn.input("Team: ")
        local pattern = vim.fn.input("Pattern: ")

        if not team or not pattern then
          vim.notify("Usage: OwnerCodeGrepPattern <team> <search-pattern>", vim.log.levels.ERROR)
          return
        end

        require("plugins-local.owner-code-search").owner_code_grep_pattern(team, pattern)
      end,
      desc = "Owner Code Grep Search",
    },
    {
      "<leader>fd",
      function()
        local team = vim.fn.input("Team: ")
        local pattern = vim.fn.input("Pattern: ")

        if not team or not pattern then
          vim.notify("Usage: OwnerCodeFd <team> <search-pattern>", vim.log.levels.ERROR)
          return
        end

        require("plugins-local.owner-code-search").owner_code_fd(team, pattern)
      end,
      desc = "Owner Code Fd Search",
    },
    {
      "<leader>fD",
      function()
        local team = vim.fn.input("Team: ")
        local pattern = vim.fn.input("Pattern: ")

        if not team or not pattern then
          vim.notify("Usage: OwnerCodeFdPattern <team> <search-pattern>", vim.log.levels.ERROR)
          return
        end

        require("plugins-local.owner-code-search").owner_code_fd_pattern(team, pattern)
      end,
      desc = "Owner Code Fd Search",
    },
  },
  config = function()
    local owner_code_grep = require("plugins-local.owner-code-search").owner_code_grep

    vim.api.nvim_create_user_command("OwnerCodeGrep", owner_code_grep, {
      nargs = "+",
      desc = "Grep paths from CODEOWNERS with ripgrep",
    })

    local owner_code_grep_pattern = require("plugins-local.owner-code-search").owner_code_grep_pattern

    vim.api.nvim_create_user_command("OwnerCodeGrepPattern", owner_code_grep_pattern, {
      nargs = "+",
      desc = "Grep path patterns from CODEOWNERS with ripgrep",
    })

    local owner_code_fd = require("plugins-local.owner-code-search").owner_code_fd

    vim.api.nvim_create_user_command("OwnerCodeFd", owner_code_fd, {
      nargs = "+",
      desc = "Find paths from CODEOWNERS with fd",
    })

    local owner_code_fd_pattern = require("plugins-local.owner-code-search").owner_code_fd_pattern

    vim.api.nvim_create_user_command("OwnerCodeFdPattern", owner_code_fd_pattern, {
      nargs = "+",
      desc = "Find path patterns from CODEOWNERS with fd",
    })
  end,
}
