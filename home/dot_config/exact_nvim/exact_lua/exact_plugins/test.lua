return {
  "nvim-neotest/neotest",
  dependencies = { "nvim-treesitter/nvim-treesitter", "haydenmeade/neotest-jest" },
  keys = {
    {
      "<leader>tl",
      function()
        require("neotest").run.run_last()
      end,
      desc = "Run Last Test",
    },
  },
  opts = function(_, opts)
    opts.discovery = {
      enabled = false,
    }
    table.insert(
      opts.adapters,
      require("neotest-jest")({
        env = { CI = true, NODE_ENV = "test" },
        jest_test_discovery = false,
        jestConfigFile = function(file)
          local dir = vim.fn.fnamemodify(file, ":h")

          while dir ~= "/" do
            local tsConfigPath = dir .. "/jest.config.ts"
            local jsConfigPath = dir .. "/jest.config.js"
            if vim.fn.filereadable(tsConfigPath) == 1 then
              return tsConfigPath
            elseif vim.fn.filereadable(jsConfigPath) == 1 then
              return jsConfigPath
            end
            dir = vim.fn.fnamemodify(dir, ":h")
          end

          local defaultTsConfigPath = vim.fn.getcwd() .. "/jest.config.ts"
          local defaultJsConfigPath = vim.fn.getcwd() .. "/jest.config.js"
          if vim.fn.filereadable(defaultTsConfigPath) == 1 then
            return defaultTsConfigPath
          elseif vim.fn.filereadable(defaultJsConfigPath) == 1 then
            return defaultJsConfigPath
          end

          return nil
        end,
        jestCommand = function()
          local packageJson = vim.fn.filereadable("package.json")

          if packageJson == 0 then
            error("package.json not found")
          end

          local yarnLock = vim.fn.filereadable("yarn.lock")
          local packageLock = vim.fn.filereadable("package-lock.json")

          if yarnLock == 1 and packageLock == 1 then
            error("both yarn.lock and package-lock.json found, please remove one")
          end

          if yarnLock == 0 and packageLock == 0 then
            error("yarn.lock or package-lock.json not found")
          end

          local packageJsonContents = vim.fn.readfile("package.json")
          local scripts = vim.fn.json_decode(packageJsonContents)["scripts"]

          local cmd = ""

          if scripts["test"] ~= nil and scripts["test"] ~= "" then
            cmd = "test"
          end

          if scripts["test:unit"] ~= nil and scripts["test:unit"] ~= "" then
            cmd = "test:unit"
          end

          if scripts["test:jest"] ~= nil and scripts["test:jest"] ~= "" then
            cmd = "test:jest"
          end

          if cmd == "" then
            error("no test script found in package.json")
          end

          local executable = ""

          if packageLock == 1 then
            executable = "npm"
          end

          if yarnLock == 1 then
            executable = "yarn"
          end

          return executable .. " run " .. cmd
        end,
        cwd = function()
          return vim.fn.getcwd()
        end,
      })
    )
  end,
}
