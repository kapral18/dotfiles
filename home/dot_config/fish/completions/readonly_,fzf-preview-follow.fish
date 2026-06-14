complete -c ',fzf-preview-follow' -l file -r -a '(__fish_complete_path)' -d 'File to preview'
complete -c ',fzf-preview-follow' -l line -r -d 'Line number to center'
complete -c ',fzf-preview-follow' -a '(__fish_complete_path)' -d 'Fallback fzf entry'
