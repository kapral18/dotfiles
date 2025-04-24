## Function: appid
function appid --description "Get the application ID from the bundle identifier"
    if test (count $argv) -eq 0
        echo "Usage: appid <bundle_id>"
        return
    end

    set -l bundle_id $argv[1]
    set -l app_id (osascript -e "id of app \"$bundle_id\"")
    echo $app_id
end

## Function: dumputi
function dumputi --description "Dump list of Uniform Type Identifiers (UTIs)"
    /System/Library/Frameworks/CoreServices.framework/Versions/A/Frameworks/LaunchServices.framework/Versions/A/Support/lsregister -dump \
        | grep "uti:" \
        | awk '{print $2}' \
        | sort \
        | uniq
end
