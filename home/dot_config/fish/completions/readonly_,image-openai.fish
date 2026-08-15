# Completions for ,image-openai.

complete -c ',image-openai' -f
complete -c ',image-openai' -s i -l input -d 'Input image (repeatable; metadata stripped before upload)' -r
complete -c ',image-openai' -l mask -d 'Edit mask for the first input image' -r
complete -c ',image-openai' -s o -l output -d 'Output file path' -r
complete -c ',image-openai' -s q -l quality -d 'Rendering quality' -x -a 'auto low medium high'
complete -c ',image-openai' -s s -l size -d 'Output size: auto or WIDTHxHEIGHT' -x -a 'auto 1024x1024 1536x1024 1024x1536 2048x2048 2048x1152 3840x2160 2160x3840'
complete -c ',image-openai' -s f -l format -d 'Output format' -x -a 'png jpeg webp'
complete -c ',image-openai' -s c -l compression -d 'JPEG/WebP compression from 0 to 100' -x
complete -c ',image-openai' -s b -l background -d 'Background handling' -x -a 'auto opaque'
complete -c ',image-openai' -s h -l help -d 'Show help'
complete -c ',image-openai' -l version -d 'Show version'
