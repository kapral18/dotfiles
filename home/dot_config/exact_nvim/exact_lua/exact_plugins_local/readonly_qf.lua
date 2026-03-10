local fs_util = require("util.fs")
local qf = require("plugins_local_src.qf")

vim.api.nvim_create_user_command("QFCopyPaths", function(opts)
  qf.copy_qf_paths_to_clipboard()
end, {
  desc = "Copy quickfix paths to clipboard",
  nargs = "*",
})

vim.api.nvim_create_user_command("QFDedupe", function(opts)
  qf.dedupe_qf_by_path()
end, {
  desc = "Dedupe quickfix list by path (keep first)",
  nargs = 0,
})

vim.api.nvim_create_user_command("QFCdoReverse", function(opts)
  qf.cdo_reverse(opts.args)
end, {
  desc = "Execute command on quickfix entries in reverse order",
  nargs = 1,
})

return {
  {
    "romainl/vim-qf",
    lazy = false,
    init = function()
      -- enable ack style mappings
      vim.g.qf_mapping_ack_style = 1
      -- disable auto quit if qf window is the only window
      vim.g.qf_auto_quit = 0
      -- if the path is too long, shorten each component to the first 3 chars
      vim.g.qf_shorten_path = 3
      -- disable auto resize
      vim.g.qf_auto_resize = 0

      vim.cmd([[
        if !exists('*ExactQfRejectKeepOpen')
          function! ExactQfRejectKeepOpen(pat, lnum1, lnum2, cnt) abort
            let l:is_loc = get(b:, 'qf_isLoc', 0)
            call qf#filter#FilterList(a:pat, 1, a:lnum1, a:lnum2, a:cnt)

            if l:is_loc
              if getloclist(0, { 'winid': 0 }).winid == 0
                lopen
              endif
            else
              if getqflist({ 'winid': 0 }).winid == 0
                copen
              endif
            endif
          endfunction
        endif

        if !exists('*ExactQfKeepKeepOpen')
          function! ExactQfKeepKeepOpen(pat, lnum1, lnum2, cnt) abort
            let l:is_loc = get(b:, 'qf_isLoc', 0)
            call qf#filter#FilterList(a:pat, 0, a:lnum1, a:lnum2, a:cnt)

            if l:is_loc
              if getloclist(0, { 'winid': 0 }).winid == 0
                lopen
              endif
            else
              if getqflist({ 'winid': 0 }).winid == 0
                copen
              endif
            endif
          endfunction
        endif
      ]])

      local qf_overrides = vim.api.nvim_create_augroup("k18_qf_overrides", { clear = true })
      vim.api.nvim_create_autocmd("FileType", {
        group = qf_overrides,
        pattern = "qf",
        callback = function(event)
          vim.schedule(function()
            if not vim.api.nvim_buf_is_valid(event.buf) then
              return
            end

            vim.api.nvim_buf_call(event.buf, function()
              pcall(vim.cmd, "silent! delcommand Reject")
              vim.cmd("command! -buffer -range -nargs=? Reject call ExactQfRejectKeepOpen(<q-args>, <line1>, <line2>, <count>)")

              pcall(vim.cmd, "silent! delcommand Keep")
              vim.cmd("command! -buffer -range -nargs=? Keep call ExactQfKeepKeepOpen(<q-args>, <line1>, <line2>, <count>)")
            end)
          end)
        end,
      })
    end,
  },
  {
    dir = fs_util.get_plugin_src_dir(),
    keys = {
      {
        "<leader>rqi",
        function()
          local pattern = vim.fn.input("Pattern(include): ")

          if pattern then
            qf.filter_qf_items_by_pattern(pattern, false)
          else
            print("No pattern provided")
          end
        end,
        desc = "Filter Quickfix Items by Pattern",
      },
      {
        "<leader>rqx",
        function()
          local pattern = vim.fn.input("Pattern(exclude): ")

          if pattern then
            qf.filter_qf_items_by_pattern(pattern, true)
          else
            print("No pattern provided")
          end
        end,
        desc = "Exclude Quickfix Items by Pattern",
      },
      {
        "dd",
        function()
          qf.remove_qf_item()
        end,
        desc = "Remove Quickfix Item",
        ft = { "qf" },
      },
    },
  },
}
