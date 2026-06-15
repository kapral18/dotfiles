complete -c ,nano-banana -s h -l help -d "Show help" -f
complete -c ,nano-banana -s o -l output -d "Output file path" -r
complete -c ,nano-banana -s m -l model -d "Model id (default: gemini-3.1-flash-image)" -x
complete -c ,nano-banana -s a -l aspect-ratio -d "Aspect ratio (default: model's choice)" -x -a "1:1 3:2 2:3 3:4 4:3 4:5 5:4 9:16 16:9 21:9"
complete -c ,nano-banana -s s -l size -d "Image resolution (default: model's choice)" -x -a "512 1K 2K 4K"
