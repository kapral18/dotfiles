complete -c appid --no-files \
    -d "Get bundle ID from app name" \
    -a "(mdfind 'kMDItemContentType == com.apple.application-bundle' | xargs -I {} basename {} .app)"
