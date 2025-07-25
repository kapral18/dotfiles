local utils = require("fzf-lua.utils")

local common_utils = require("utils.common")

---@class LspItem
---@field filename string Path to the file
---@field lnum number Line number
---@field col number Column number
---@field end_lnum number End line number
---@field end_col number End column number
---@field text string The actual code content/text
---@field user_data table Additional LSP data with uri and range

local M = {}
local owner_fmt = {
  enrich = function(opts, version)
    -- Configure fzf for multiline with proper alignment
    opts.fzf_opts = vim.tbl_extend("keep", opts.fzf_opts or {}, {
      ["--tabstop"] = 1,
      ["--read0"] = true, -- for null-separated multiline entries
    })

    -- For version 2: disable horizontal scrolling for better multiline display
    if tonumber(version) == 2 then
      opts.fzf_opts = vim.tbl_extend("keep", opts.fzf_opts or {}, {
        ["--ellipsis"] = " ",
        ["--no-hscroll"] = true,
      })
    end

    return opts
  end,
  _to = function()
    return [[
            return function(filepath, opts, context)
                local sfo = require("plugins-local-src.show-file-owner")

                -- Get owner information
                local owner = sfo.get_file_owner(filepath)
                if owner then
                    -- Create multiline entry: owner(s) on first line, filename on second line
                    return "[" .. owner .. "]\n" .. filepath
                else
                    -- No owner, just return filename
                    return filepath
                end
            end
        ]]
  end,
  from = function(entry_string, _)
    -- Remove ANSI codes first
    local clean_entry = utils.strip_ansi_coloring(entry_string)

    -- Handle multiline entries - extract the second line (filename)
    local lines = vim.split(clean_entry, "\n")

    -- If multiline, return the second line (filename)
    -- If single line, return as is
    if #lines >= 2 then
      return lines[2] -- Second line contains the filename
    else
      return lines[1] or clean_entry
    end
  end,
}

-- Language-specific file ignore patterns
local js_ts_file_patterns = {
  ["No non-source files"] = { "test", "%.test%.", "spec", "%.spec%.", "%.snap", "node_modules", "%.d%.ts" },
  ["No test files"] = { "test", "%.test%.", "spec", "%.spec%.", "%.snap" },
  ["No node_modules"] = { "node_modules" },
  ["No .d.ts files"] = { "%.d%.ts" },
  ["No .snap files"] = { "%.snap" },
  ["No hidden files"] = { "^%." },
  ["Custom input"] = "$$input$$",
  ["No filtering"] = {},
}

local js_ts_content_patterns = {
  ["No imports"] = { "^%s*import .*%{", "^%s*require%(", "^.* from [\"']" },
  ["Custom input"] = "$$input$$",
  ["No filtering"] = {},
}

---@type table<string, {files: table<string, string[]>, content: table<string, string[]>}>
local file_ignore_pattern_presets = {
  javascript = { files = js_ts_file_patterns, content = js_ts_content_patterns },
  typescript = { files = js_ts_file_patterns, content = js_ts_content_patterns },
  tsx = { files = js_ts_file_patterns, content = js_ts_content_patterns },
  jsx = { files = js_ts_file_patterns, content = js_ts_content_patterns },
  javascriptreact = { files = js_ts_file_patterns, content = js_ts_content_patterns },
  typescriptreact = { files = js_ts_file_patterns, content = js_ts_content_patterns },
  none = { files = { ["No filtering"] = {} }, content = { ["No filtering"] = {} } },
}

-- Helper function to handle custom input
---@param patterns string[]|string The patterns to choose from or custom input trigger
---@param callback fun(final_patterns: string[]) Callback function to handle the final patterns
local function handle_custom_input(patterns, callback)
  if patterns == "$$input$$" then
    vim.ui.input({
      prompt = "Enter pattern: ",
    }, function(custom_pattern)
      if custom_pattern and custom_pattern ~= "" then
        callback({ custom_pattern })
      else
        callback({})
      end
    end)
  else
    callback(patterns --[[@as string[] ]])
  end
end

-- Enhanced LSP function with owner information in entries
---@param lsp_function function The fzf-lua LSP function to call
---@param method_name string Display name for the LSP method
---@param opts? table Additional options
local function enhanced_lsp_function(lsp_function, method_name, opts)
  opts = opts or {}

  local ft = vim.bo.filetype
  local file_presets = file_ignore_pattern_presets[ft] and file_ignore_pattern_presets[ft].files
    or file_ignore_pattern_presets.none.files
  local content_presets = file_ignore_pattern_presets[ft] and file_ignore_pattern_presets[ft].content
    or file_ignore_pattern_presets.none.content

  -- Get available file patterns
  local file_pattern_labels = vim.tbl_keys(file_presets)
  table.sort(file_pattern_labels)

  vim.ui.select(file_pattern_labels, {
    prompt = "Select file ignore patterns:",
    kind = "file_patterns",
  }, function(file_choice)
    if not file_choice then
      return
    end

    local selected_file_patterns = file_presets[file_choice]

    handle_custom_input(selected_file_patterns, function(final_file_patterns)
      -- Get available content patterns
      local content_pattern_labels = vim.tbl_keys(content_presets) --[[@as string[] ]]
      table.sort(content_pattern_labels)

      vim.ui.select(content_pattern_labels, {
        prompt = "Select content filter:",
        kind = "content_patterns",
      }, function(content_choice)
        if not content_choice then
          return
        end

        local selected_content_patterns = content_presets[content_choice]

        handle_custom_input(selected_content_patterns, function(final_content_patterns)
          local content_filter_predicate
          if final_content_patterns and #final_content_patterns > 0 then
            -- Build content filter predicate that works with LSP item objects
            ---@param item LspItem The LSP item object
            ---@return boolean true to keep the item, false to filter it out
            content_filter_predicate = function(item)
              -- The item is a table with filename, lnum, col, text, etc.
              local text = item.text or ""
              for _, pattern in ipairs(final_content_patterns) do
                if text:match(pattern) then
                  return false -- drop this entry
                end
              end
              return true -- keep
            end
          end

          -- Call the fzf-lua LSP function with enhanced configuration
          local fzf_opts = vim.tbl_deep_extend("force", common_utils.get_fzf_opts()(), {
            prompt = opts.prompt_name or method_name,
            multiline = 3, -- Now we have 3 lines: owners, file info, code content
            file_ignore_patterns = final_file_patterns,
            jump1 = true,
            ignore_current_line = true,
            unique_line_items = true,
            regex_filter = content_filter_predicate,
            formatter = "owner_fmt",
          })

          -- Use fzf-lua's native LSP function
          lsp_function(fzf_opts)
        end)
      end)
    end)
  end)
end

-- Convenience functions using fzf-lua's native LSP functions
M.definitions = function()
  enhanced_lsp_function(require("fzf-lua").lsp_definitions, "Definitions")
end

M.references = function()
  enhanced_lsp_function(require("fzf-lua").lsp_references, "References")
end

M.implementations = function()
  enhanced_lsp_function(require("fzf-lua").lsp_implementations, "Implementations")
end

M.type_definitions = function()
  enhanced_lsp_function(require("fzf-lua").lsp_typedefs, "Type Definitions")
end

return {
  "ibhagwan/fzf-lua",
  dependencies = { "nvim-tree/nvim-web-devicons" },
  opts = {
    formatters = {
      owner_fmt = owner_fmt,
    },
  },
  keys = {
    {
      "<leader>gd",
      function()
        M.definitions()
      end,
      desc = "Interactive Filtered Definitions",
    },
    {
      "<leader>gr",
      function()
        M.references()
      end,
      desc = "Interactive Filtered References",
    },
    {
      "<leader>gI",
      function()
        M.implementations()
      end,
      desc = "Interactive Filtered Implementations",
    },
    {
      "<leader>gy",
      function()
        M.type_definitions()
      end,
      desc = "Interactive Filtered Type Definitions",
    },
  },
}
