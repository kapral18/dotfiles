# Completions for ,image-openrouter.

function __image_openrouter_models
    printf '%s\t%s\n' \
        bytedance-seed/seedream-5-0-pro 'Default; quality/value; generation/editing; 1K/2K' \
        bytedance-seed/seedream-5-0-lite 'High-resolution value; generation/editing; 2K/4K' \
        'google/gemini-3.1-flash-lite-image' 'Fast 1K value; generation/editing' \
        'google/gemini-3.1-flash-image' 'Google generation/editing; 512/1K/2K/4K' \
        'microsoft/mai-image-2.5' 'Single-reference generation/editing'
end

complete -c ',image-openrouter' -f
complete -c ',image-openrouter' -s i -l input -d 'Local reference image (repeatable; metadata stripped before upload)' -r
complete -c ',image-openrouter' -s o -l output -d 'Output file path (suffix follows returned media type)' -r
complete -c ',image-openrouter' -s m -l model -d 'Select a curated ZDR image model' -x -a '(__image_openrouter_models)'
complete -c ',image-openrouter' -s a -l aspect-ratio -d 'Aspect ratio supported by the model (for example 1:1 or 16:9)' -x
complete -c ',image-openrouter' -s r -l resolution -d 'Resolution supported by the model (for example 1K or 2K)' -x
complete -c ',image-openrouter' -s h -l help -d 'Show help'
complete -c ',image-openrouter' -l version -d 'Show version'
