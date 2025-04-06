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
          vim.notify("Usage: OwnerFolderSearch <team> <search-pattern>", vim.log.levels.ERROR)
          return
        end

        require("plugins-local.owner-folder-search").owner_folder_search(team, pattern)
      end,
      desc = "Owner Folder Search",
    },
  },
  config = function()
    local owner_folder_search = require("plugins-local.owner-folder-search").owner_folder_search

    vim.api.nvim_create_user_command("OwnerFolderSearch", owner_folder_search, {
      nargs = "+",
      desc = "Search owned directories from CODEOWNERS with ripgrep",
    })
  end,
}
