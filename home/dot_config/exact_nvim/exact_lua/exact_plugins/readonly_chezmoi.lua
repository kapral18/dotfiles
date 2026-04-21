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
      -- Instead of fighting registration order, listen for a `FileType`
      -- change on any buffer under the chezmoi source tree and, if the
      -- resulting filetype is one of the known hijackers, re-run
      -- chezmoi.vim's detection so the correct composite filetype
      -- (`<ft>.chezmoitmpl`) gets assigned.
      local hijack_fts = {
        gotexttmpl = true,
        gohtmltmpl = true,
      }
      local group = vim.api.nvim_create_augroup("chezmoi_reclaim_filetype", { clear = true })
      vim.api.nvim_create_autocmd("FileType", {
        group = group,
        callback = function(ev)
          if not hijack_fts[ev.match] then
            return
          end
          local source_dir = vim.g["chezmoi#source_dir_path"]
          if type(source_dir) ~= "string" or source_dir == "" then
            return
          end
          local name = vim.api.nvim_buf_get_name(ev.buf)
          if name == "" or name:find(source_dir, 1, true) ~= 1 then
            return
          end
          if vim.fn.exists("#chezmoi_filetypedetect") ~= 1 then
            return
          end
          vim.api.nvim_buf_call(ev.buf, function()
            pcall(vim.cmd, "unlet! b:chezmoi_handling")
            pcall(vim.cmd, "unlet! b:chezmoi_detecting_fixed")
            pcall(vim.cmd, "doautocmd chezmoi_filetypedetect BufRead " .. vim.fn.fnameescape(name))
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
