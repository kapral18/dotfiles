return {
  {
    "mfussenegger/nvim-lint",
    event = "BufReadPost",
    opts = function(_, opts)
      opts.events = { "BufWritePost", "BufReadPost", "InsertLeave" }
      opts.linters_by_ft = opts.linters_by_ft or {}
      opts.linters = opts.linters or {}
      return opts
    end,
    config = function(_, opts)
      local augroup = vim.api.nvim_create_augroup("nvim-lint", { clear = true })
      local lint = require("lint")

      -- reset default linters
      lint.linters_by_ft = {}

      for name, linter in pairs(opts.linters or {}) do
        local registered = lint.linters[name]
        if type(linter) == "table" and type(registered) == "table" then
          lint.linters[name] = vim.tbl_deep_extend("force", registered, linter)
          if type(linter.prepend_args) == "table" then
            lint.linters[name].args = lint.linters[name].args or {}
            vim.list_extend(lint.linters[name].args, linter.prepend_args)
          end
        else
          lint.linters[name] = linter
        end
      end

      lint.linters_by_ft = vim.tbl_deep_extend("force", lint.linters_by_ft or {}, opts.linters_by_ft or {})

      local function debounce(ms, fn)
        local timer = vim.uv.new_timer()
        return function(...)
          local argv = { ... }
          timer:start(ms, 0, function()
            timer:stop()
            vim.schedule_wrap(fn)(unpack(argv))
          end)
        end
      end

      local function run_lint()
        local names = lint._resolve_linter_by_ft(vim.bo.filetype)
        names = vim.list_extend({}, names)

        if #names == 0 then
          vim.list_extend(names, lint.linters_by_ft["_"] or {})
        end
        vim.list_extend(names, lint.linters_by_ft["*"] or {})

        local ctx = {
          filename = vim.api.nvim_buf_get_name(0),
        }
        ctx.dirname = vim.fn.fnamemodify(ctx.filename, ":h")

        names = vim.tbl_filter(function(name)
          local linter = lint.linters[name]
          if not linter then
            vim.notify("Linter not found: " .. name, vim.log.levels.WARN, { title = "nvim-lint" })
            return false
          end
          if type(linter) == "table" and linter.condition then
            local ok, ret = pcall(linter.condition, ctx)
            if not ok or not ret then
              return false
            end
          end
          return true
        end, names)

        if #names > 0 then
          lint.try_lint(names)
        end
      end

      vim.api.nvim_create_autocmd(opts.events or {}, {
        group = augroup,
        callback = debounce(100, run_lint),
      })
    end,
  },
}
