complete -c ,to-gif -s i -l input -d "Input video file" -r -a "(__fish_complete_path)"
complete -c ,to-gif -s o -l output -d "Output GIF file" -r -a "(__fish_complete_suffix .gif)"
complete -c ,to-gif -s t -l time -d "Duration in seconds (default: 35)" -r
complete -c ,to-gif -s s -l scale -d "Scale width in pixels (default: 680)" -r
complete -c ,to-gif -s f -l fps -d "Frames per second (default: 25)" -r
complete -c ,to-gif -s p -l pts -d "setpts factor multiplier (default: 0.8)" -r
complete -c ,to-gif -s h -l help -d "Display help"
