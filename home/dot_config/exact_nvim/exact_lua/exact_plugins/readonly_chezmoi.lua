return {
  {
    "alker0/chezmoi.vim",
    version = false,
    init = function()
      -- This option is required.
      vim.g["chezmoi#use_tmp_buffer"] = true
      -- add other options here if needed.
      vim.g["chezmoi#use_tmp_buffer"] = 1
      vim.g["chezmoi#source_dir_path"] = os.getenv("HOME") .. "/.local/share/chezmoi"

      -- Redirect LSP definition/reference jumps to chezmoi source files when
      -- navigating from inside the source tree (instead of the deployed target
      -- that `chezmoi apply` overwrites). Safe to install eagerly; idempotent.
      require("util.chezmoi_lsp").setup()

      -- Defensive filetype reclaim for chezmoi `.tmpl` source files.
      --
      -- Other plugins ship blanket `au *.tmpl set filetype=<X>` rules in
      -- their `ftdetect/` (notably `ray-x/go.nvim` -> `gotexttmpl`). Lazy
      -- sources every plugin's `ftdetect/` eagerly at startup, so those
      -- autocmds are registered before any buffer is read. When both the
      -- blanket rule and `alker0/chezmoi.vim`'s per-source-dir rule fire
      -- on the same BufRead, the later-registered one wins; if that's the
      -- blanket rule, a chezmoi template ends up with the wrong filetype
      -- (and thus the wrong syntax, e.g. `goCharacter` matching stray `'`
      -- in gitconfig comments/values).
      --
      -- Instead of deleting the global `*.tmpl` rule, only reclaim buffers
      -- under the chezmoi source tree. chezmoi.vim has already recorded the
      -- target filetype in `b:chezmoi_original_filetype`; restore that
      -- composite filetype after the hijacker finishes.
      local hijack_fts = {
        gotexttmpl = true,
        gohtmltmpl = true,
      }
      local comment_prefixes_by_ft = {
        bash = { "#" },
        conf = { "#" },
        dotenv = { "#" },
        fish = { "#" },
        gitconfig = { "#", ";" },
        ini = { "#", ";" },
        jsonc = { "//" },
        lua = { "--" },
        python = { "#" },
        ruby = { "#" },
        sh = { "#" },
        toml = { "#" },
        yaml = { "#" },
        zsh = { "#" },
      }

      local function escaped_pattern(text)
        return (text:gsub("([^%w])", "%%%1"))
      end

      local function comment_prefixes(filetype)
        if type(filetype) ~= "string" or filetype == "" then
          return nil
        end
        return comment_prefixes_by_ft[filetype] or comment_prefixes_by_ft[filetype:match("^[^.]+")]
      end

      local function template_syntax_is_comment_wrapped(bufnr, filetype)
        local prefixes = comment_prefixes(filetype)
        if not prefixes then
          return false
        end

        local saw_template = false
        for _, line in ipairs(vim.api.nvim_buf_get_lines(bufnr, 0, -1, false)) do
          if line:find("{{", 1, true) or line:find("}}", 1, true) then
            saw_template = true
            local is_comment_directive = false
            for _, prefix in ipairs(prefixes) do
              if line:find("^%s*" .. escaped_pattern(prefix)) then
                is_comment_directive = true
                break
              end
            end
            if not is_comment_directive then
              return false
            end
          end
        end

        return saw_template
      end

      local function source_dir()
        local dir = vim.g["chezmoi#source_dir_path"]
        if type(dir) ~= "string" or dir == "" then
          return nil
        end
        return dir:gsub("/+$", "")
      end

      local function is_under_source_dir(name, dir)
        return name == dir or name:sub(1, #dir + 1) == dir .. "/"
      end

      local function is_source_template(name)
        local dir = source_dir()
        return dir ~= nil and name ~= "" and is_under_source_dir(name, dir) and name:sub(-5) == ".tmpl"
      end

      local function valid_native_filetype(filetype)
        return type(filetype) == "string"
          and filetype ~= ""
          and filetype ~= "chezmoitmpl"
          and not hijack_fts[filetype]
          and not filetype:find("chezmoitmpl", 1, true)
      end

      local function native_filetype(bufnr, name)
        local original_ft = vim.b[bufnr].chezmoi_original_filetype
        if valid_native_filetype(original_ft) then
          return original_ft
        end

        local stripped_name = name:gsub("%.tmpl$", "")
        local matched_ft = vim.filetype.match({ filename = stripped_name, buf = bufnr })
        if valid_native_filetype(matched_ft) then
          return matched_ft
        end
      end

      local function target_template_filetype(bufnr, name)
        if vim.fn.fnamemodify(name, ":t") == "readonly_dot_Brewfile.tmpl" then
          return "conf"
        end

        local native_ft = native_filetype(bufnr, name)
        if native_ft then
          if template_syntax_is_comment_wrapped(bufnr, native_ft) then
            return native_ft
          end
          return native_ft .. ".chezmoitmpl"
        end

        return "chezmoitmpl"
      end

      local function apply_template_filetype(bufnr)
        if not vim.api.nvim_buf_is_valid(bufnr) then
          return
        end

        local name = vim.api.nvim_buf_get_name(bufnr)
        if not is_source_template(name) then
          return
        end

        local target_ft = target_template_filetype(bufnr, name)
        if vim.bo[bufnr].filetype ~= target_ft then
          vim.bo[bufnr].filetype = target_ft
        end
      end

      local group = vim.api.nvim_create_augroup("chezmoi_reclaim_filetype", { clear = true })
      vim.api.nvim_create_autocmd({ "BufReadPost", "BufNewFile" }, {
        group = group,
        pattern = "*.tmpl",
        callback = function(ev)
          vim.schedule(function()
            apply_template_filetype(ev.buf)
          end)
        end,
      })
      vim.api.nvim_create_autocmd("FileType", {
        group = group,
        callback = function(ev)
          if not hijack_fts[ev.match] then
            return
          end
          vim.schedule(function()
            apply_template_filetype(ev.buf)
          end)
        end,
      })
    end,
  },
  -- Filetype icons
  {
    "nvim-mini/mini.icons",
    version = "*",
    opts = {
      file = {
        [".chezmoiignore"] = { glyph = "", hl = "MiniIconsGrey" },
        [".chezmoiremove"] = { glyph = "", hl = "MiniIconsGrey" },
        [".chezmoiroot"] = { glyph = "", hl = "MiniIconsGrey" },
        [".chezmoiversion"] = { glyph = "", hl = "MiniIconsGrey" },
        ["bash.tmpl"] = { glyph = "", hl = "MiniIconsGrey" },
        ["json.tmpl"] = { glyph = "", hl = "MiniIconsGrey" },
        ["ps1.tmpl"] = { glyph = "󰨊", hl = "MiniIconsGrey" },
        ["sh.tmpl"] = { glyph = "", hl = "MiniIconsGrey" },
        ["toml.tmpl"] = { glyph = "", hl = "MiniIconsGrey" },
        ["yaml.tmpl"] = { glyph = "", hl = "MiniIconsGrey" },
        ["zsh.tmpl"] = { glyph = "", hl = "MiniIconsGrey" },
      },
    },
  },
}
