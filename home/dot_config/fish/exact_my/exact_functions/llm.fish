## Function: get_source_for_llm
function get_source_for_llm --description "Get source code files for language models"
    fd -e ts -e tsx -E '*test*' -E '*mock*' -E 'setup_tests.ts' -E target --search-path $argv[1] -0 \
        | while read -lz file
        echo "===== $file ====="
        cat "$file"
        echo
    end | pbcopy
end

## Function: get_tests_for_llm
function get_tests_for_llm --description "Get test files for language models"
    fd -e ts -e tsx -p '(/mock/|/stub/|\.test\.)' -E 'setup_tests.ts' -E target --search-path $argv[1] -0 \
        | while read -lz file
        echo "===== $file ====="
        cat "$file"
        echo
    end | pbcopy
end
