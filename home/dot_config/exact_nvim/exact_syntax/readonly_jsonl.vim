" Vim syntax file
" Language:         JSONL (JSON Lines)
" Origin:          kyoh86/vim-jsonl (MIT) — JSON syntax with cross-line
"                  missing-comma error suppressed for newline-delimited records.

if exists('b:current_syntax')
  finish
endif

let s:cpo_save = &cpoptions
set cpoptions&vim

let main_syntax = 'jsonl'

runtime syntax/json.vim

syntax clear jsonMissingCommaError

syn match jsonMissingCommaError /\("\|\]\|\d\)\zs\_s\+\ze"/
syn match jsonMissingCommaError /\(\]\|\}\)\_s\+\ze"/
syn match jsonMissingCommaError /\(true\|false\)\_s\+\ze"/

unlet main_syntax
let b:current_syntax = 'jsonl'

let &cpoptions = s:cpo_save
unlet s:cpo_save
