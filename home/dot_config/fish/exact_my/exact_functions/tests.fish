## Function: get_risky_tests
function get_risky_tests --description "Get tests close to or beyond default Jest threshold"
    if test (count $argv) -eq 0
        echo "Usage: get_risky_tests <folder_path>"
        return
    end

    set temp_output (mktemp -t jest-output)

    cpulimit -l 2 -i -- node --max-old-space-size=12288 --trace-warnings scripts/jest $argv[1] \
        --runInBand --coverage=false --passWithNoTests --silent --ci --json --outputFile=$temp_output

    cat $temp_output | jq "
        .testResults[] as \$test |
        \$test.assertionResults[] |
        select(.duration > 4000) |
        {fullPath: \$test.name, fullName: .fullName, duration: .duration}
    "
end
