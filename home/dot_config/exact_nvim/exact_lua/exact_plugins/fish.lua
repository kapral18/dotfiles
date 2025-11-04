local chezmoi = require("util.chezmoi")
local uv = vim.uv or vim.loop

local function build_formatter()
  local default = require("conform.formatters.fish_indent")
  local command = default.command
  local args = default.args or {}

  return {
    meta = default.meta,
    format = function(_, ctx, lines, callback)
      if not command or command == "" then
        callback("fish_indent formatter command not configured")
        return
      end
      local bufnr = ctx.bufnr or ctx.buf or 0
      local prep = chezmoi.prepare_format_input(lines, bufnr)
      local cmd = { command }
      vim.list_extend(cmd, args)

      local ok, err = pcall(
        vim.system,
        cmd,
        {
          stdin = prep.text,
          text = true,
          cwd = ctx.dirname,
        },
        vim.schedule_wrap(function(result)
          if result.code ~= 0 then
            local stderr = result.stderr
            if not stderr or stderr == "" then
              stderr = string.format("fish_indent exited with code %d", result.code)
            end
            callback(stderr)
            return
          end

          local new_lines = chezmoi.restore_formatted_text(result.stdout or "", {
            replacements = prep.replacements,
            had_eol = prep.had_eol,
            original_lines = prep.original_lines,
          })
          callback(nil, new_lines)
        end)
      )

      if not ok then
        callback(err)
      end
    end,
  }
end

local function build_linter()
  local base = require("lint.linters.fish")
  local parser = base.parser

  local function get_source_path(bufnr, default)
    local ok, source = pcall(vim.api.nvim_buf_get_var, bufnr, "chezmoi_source_path")
    if ok and type(source) == "string" and source ~= "" then
      return source
    end
    return default
  end

  local function render_template(path)
    local system_ok, handle = pcall(vim.system, { "chezmoi", "execute-template", "--source-path", path }, { text = true })
    if not system_ok or not handle then
      return nil, "chezmoi execute-template failed to start"
    end
    local result = handle:wait()
    if result.code ~= 0 then
      local stderr = (result.stderr or ""):gsub("%s+$", "")
      if stderr == "" then
        stderr = ("chezmoi execute-template exited with code %d"):format(result.code)
      end
      return nil, stderr
    end
    return result.stdout or "", nil
  end

  return function()
    local bufnr = vim.api.nvim_get_current_buf()
    local lines = vim.api.nvim_buf_get_lines(bufnr, 0, -1, true)
    local prep = chezmoi.prepare_format_input(lines, bufnr)
    local tmpname = vim.fn.tempname() .. ".fish"
    local source_path = get_source_path(bufnr, prep.original_lines and vim.api.nvim_buf_get_name(bufnr) or "")

    local rendered, render_err = render_template(source_path)
    local wrote_tmp = false
    local write_err

    if rendered and rendered ~= "" then
      wrote_tmp, write_err = pcall(function()
        local fd = assert(uv.fs_open(tmpname, "w", 448))
        assert(uv.fs_write(fd, rendered))
        uv.fs_close(fd)
      end)
    end

    if not wrote_tmp then
      local content = prep.text or table.concat(lines, "\n")
      local fallback_lines = vim.split(content, "\n", { plain = true })
      wrote_tmp, write_err = pcall(vim.fn.writefile, fallback_lines, tmpname, "b")
    end

    if not wrote_tmp then
      local message = write_err or render_err or "unknown error"
      vim.schedule(function()
        vim.notify(
          ("chezmoi fish lint: failed to prepare temporary file (%s)"):format(message),
          vim.log.levels.WARN
        )
      end)
      return base
    end

    local linter = vim.tbl_extend("force", {}, base, {
      args = { "--no-execute", tmpname },
      stdin = false,
      append_fname = false,
      name = "chezmoi_fish",
    })
    linter.parser = function(output, target_bufnr, cwd)
      local diagnostics = parser(output, target_bufnr, cwd)
      vim.schedule(function()
        pcall(vim.fn.delete, tmpname)
      end)
      return diagnostics
    end

    vim.defer_fn(function()
      pcall(vim.fn.delete, tmpname)
    end, 5000)

    return linter
  end
end

return {
  {
    "nvim-treesitter/nvim-treesitter",
    opts = function(_, opts)
      opts.ensure_installed = vim.list_extend(opts.ensure_installed or {}, { "fish" })
      return opts
    end,
  },
  {
    "neovim/nvim-lspconfig",
    opts = function(_, opts)
      opts.servers = opts.servers or {}
      local server_cfg = opts.servers.fish_lsp

      if server_cfg == true or server_cfg == nil then
        server_cfg = {}
      elseif type(server_cfg) ~= "table" then
        server_cfg = {}
      else
        server_cfg = vim.deepcopy(server_cfg)
      end

      local filetypes = {}
      if type(server_cfg.filetypes) == "table" then
        filetypes = vim.list_extend({}, server_cfg.filetypes)
      end

      local function ensure_ft(ft)
        if not vim.tbl_contains(filetypes, ft) then
          table.insert(filetypes, ft)
        end
      end

      ensure_ft("fish")
      ensure_ft("fish.chezmoitmpl")

      -- Keep fish_lsp diagnostics untouched; they handle template warnings better than any filtering.
      server_cfg.filetypes = filetypes
      opts.servers.fish_lsp = server_cfg

      return opts
    end,
  },
  {
    "stevearc/conform.nvim",
    opts = function(_, opts)
      opts.formatters = vim.tbl_deep_extend("force", opts.formatters or {}, {
        chezmoi_fish_indent = build_formatter(),
      })
      opts.formatters_by_ft = vim.tbl_deep_extend("force", opts.formatters_by_ft or {}, {
        fish = { "chezmoi_fish_indent" },
        ["fish.chezmoitmpl"] = { "chezmoi_fish_indent" },
      })

      opts.formatters = opts.formatters or {}
      local stylua_cfg = opts.formatters.stylua

      local function wrap_stylua_condition(cfg)
        cfg = cfg or {}
        local previous = cfg.condition
        cfg.condition = function(self, ctx)
          local ft = ctx.filetype or ""
          if ft:find("chezmoitmpl", 1, true) then
            return false
          end
          if previous then
            return previous(self, ctx)
          end
          return true
        end
        return cfg
      end

      if type(stylua_cfg) == "function" then
        local original = stylua_cfg
        opts.formatters.stylua = function(bufnr)
          return wrap_stylua_condition(original(bufnr))
        end
      else
        opts.formatters.stylua = wrap_stylua_condition(stylua_cfg)
      end

      return opts
    end,
  },
  {
    "mfussenegger/nvim-lint",
    opts = function(_, opts)
      opts.linters = vim.tbl_deep_extend("force", opts.linters or {}, {
        chezmoi_fish = build_linter(),
      })
      opts.linters_by_ft = vim.tbl_deep_extend("force", opts.linters_by_ft or {}, {
        fish = { "chezmoi_fish" },
        ["fish.chezmoitmpl"] = { "chezmoi_fish" },
      })
      return opts
    end,
    config = function()
      local lint_ok, lint = pcall(require, "lint")
      if not lint_ok then
        return
      end

      local function notify_fish_lsp(bufnr)
        local clients = vim.lsp.get_clients({ bufnr = bufnr, name = "fish_lsp" })
        if not clients or #clients == 0 then
          return
        end
        local uri = vim.uri_from_bufnr(bufnr)
        local text = table.concat(vim.api.nvim_buf_get_lines(bufnr, 0, -1, true), "\n")
        for _, client in ipairs(clients) do
          client.notify("textDocument/didSave", {
            textDocument = { uri = uri },
            text = text,
          })
        end
      end

      local group = vim.api.nvim_create_augroup("ChezmoiFishLintRefresh", { clear = true })
      vim.api.nvim_create_autocmd("User", {
        pattern = "ConformFormatPost",
        group = group,
        callback = function(event)
          if not event.buf or not vim.api.nvim_buf_is_valid(event.buf) then
            return
          end
          local ft = vim.bo[event.buf].filetype or ""
          if not (ft:find("fish", 1, true) and ft:find("chezmoitmpl", 1, true)) then
            return
          end
          vim.defer_fn(function()
            if not vim.api.nvim_buf_is_valid(event.buf) then
              return
            end
            vim.api.nvim_buf_call(event.buf, function()
              lint.try_lint("chezmoi_fish", { ignore_errors = true })
            end)
            notify_fish_lsp(event.buf)
          end, 100)
        end,
      })
    end,
  },
}
