## Function: vid_ipad
function vid_ipad --description "Make video iPad-ready" -a input output
    ffmpeg -i $argv[1] -af "
        loudnorm=I=-14:TP=-1.5:LRA=7,
        acompressor=threshold=-20dB:ratio=4:attack=200:release=1000,
        equalizer=f=30:t=q:w=1:g=5
    " -c:v libx264 -crf 17 -preset slow -c:a aac -b:a 192k $argv[2]
end
