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
          vim.notify("Usage: OwnerCodeSearch <team> <search-pattern>", vim.log.levels.ERROR)
          return
        end

        require("plugins-local.owner-code-search").owner_code_grep(team, pattern)
      end,
      desc = "Owner Code Grep Search",
    },
    {
      "<leader>fd",
      function()
        local team = vim.fn.input("Team: ")
        local pattern = vim.fn.input("Pattern: ")

        if not team or not pattern then
          vim.notify("Usage: OwnerCodeSearch <team> <search-pattern>", vim.log.levels.ERROR)
          return
        end

        require("plugins-local.owner-code-search").owner_code_fd(team, pattern)
      end,
      desc = "Owner Code Fd Search",
    },
  },
  config = function()
    local owner_code_grep = require("plugins-local.owner-code-search").owner_code_grep

    vim.api.nvim_create_user_command("OwnerCodeGrep", owner_code_grep, {
      nargs = "+",
      desc = "Grep owned directories from CODEOWNERS with ripgrep",
    })

    local owner_code_fd = require("plugins-local.owner-code-search").owner_code_fd

    vim.api.nvim_create_user_command("OwnerCodeFd", owner_code_fd, {
      nargs = "+",
      desc = "Find owned path from CODEOWNERS with fd",
    })
  end,
}
