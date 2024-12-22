##
# Main function: venv
# Manages Python virtual environments stored under ~/.virtualenvs
# and optionally leverages 'asdf' to select Python versions.
#
# credits: https://github.com/yangchenyun/fish-config/blob/b3700e4fd91bef73fe7f1feedff9b5c7cfdd238f/pyenv.fish
##
function venv --argument-names cmd --description "Manage Python virtual environments for the current directory"
    # Ensure the .virtualenvs directory exists
    if not test -d "$HOME/.virtualenvs"
        mkdir -p "$HOME/.virtualenvs"
    end

    switch "$cmd"
        # Show help if no command or if -h/--help is given
        case "" -h --help
            _venv_help

        case new
            # Check if asdf is installed
            if not type -q asdf
                echo "Error: 'asdf' is not installed or not in PATH."
                return 1
            end

            # Get a Python version from asdf
            set -l python_list (asdf list python)
            if test -z "$python_list"
                echo "Error: No Python versions installed under asdf."
                return 1
            end

            set -l python_version (echo $python_list | fzf)
            if test -z "$python_version"
                echo "No Python version selected."
                return 1
            end

            # Check that the selected Python version is installed
            set -l python_bin asdf which python "$python_version"
            if not test -x "$python_bin"
                echo "Error: Python $python_version is not installed or not executable."
                return 1
            end

            # Derive the venv name from the current directory
            set -l venv_name (basename "$PWD" | tr . -)
            echo "Creating virtual environment '$venv_name' using Python $python_version ..."

            # Create and activate the virtual environment
            $python_bin -m venv "$HOME/.virtualenvs/$venv_name"
            _venv_activate "$venv_name"

        case activate
            # Ensure there are venvs to activate
            set -l venv_list (ls "$HOME/.virtualenvs")
            if test -z "$venv_list"
                echo "No virtual environments found."
                return 1
            end

            # Select a venv with fzf
            set -l venv_name (echo $venv_list | fzf)
            if test -z "$venv_name"
                echo "No virtual environment selected."
                return 1
            end

            _venv_activate "$venv_name"

        case deactivate
            if test -n "$VIRTUAL_ENV"
                deactivate
                echo "Virtual environment deactivated."
            else
                echo "No virtual environment is currently active."
            end

        case delete
            # Ensure there are venvs to delete
            set -l venv_list (ls "$HOME/.virtualenvs")
            if test -z "$venv_list"
                echo "No virtual environments found."
                return 1
            end

            # Pick a venv with fzf
            set -l venv_name (echo $venv_list | fzf)
            if test -z "$venv_name"
                echo "No virtual environment selected."
                return 1
            end

            echo -n "Delete virtual environment '$venv_name'? "
            if _confirm
                rm -rf "$HOME/.virtualenvs/$venv_name"
                echo "Virtual environment '$venv_name' has been deleted."
            else
                echo "Deletion cancelled."
            end

            # Unknown command
        case '*'
            echo "venv: Unknown command '$cmd'" >&2
            _venv_help
            return 1
    end
end

##
# _venv_help
# Prints out usage instructions for the 'venv' command.
##
function _venv_help
    echo "Usage: venv [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  new        Create a new virtual environment (requires 'asdf')"
    echo "  activate   Select and activate a virtual environment"
    echo "  deactivate Deactivate the current virtual environment"
    echo "  delete     Delete a virtual environment"
    echo ""
    echo "Options:"
    echo "  -h, --help Show this help message"
end

##
# _venv_activate <venv_name>
# Activates an existing virtual environment by name.
##
function _venv_activate --argument-names venv_name
    set -l venv_path "$HOME/.virtualenvs/$venv_name"
    if test -d "$venv_path" -a -x "$venv_path/bin/activate.fish"
        echo "Activating virtual environment '$venv_name' ..."
        source "$venv_path/bin/activate.fish"
    else
        echo "Error: Virtual environment '$venv_name' does not exist or is not valid."
    end
end

##
# __auto_venv
# Automatically activates/deactivates a virtual environment based on the current directory.
# Add this to your config if you want the auto-activation behavior.
##
function __auto_venv --on-variable PWD --description "Automatically manage Python virtual environments based on directory"
    set -l venv_name (basename "$PWD" | tr . -)
    set -l venv_path "$HOME/.virtualenvs/$venv_name"

    if test -d "$venv_path" -a -x "$venv_path/bin/activate.fish"
        # Activate if not already active
        if test "$VIRTUAL_ENV" != "$venv_path"
            echo "Auto-activating virtual environment '$venv_name' ..."
            source "$venv_path/bin/activate.fish"
        end
    else if test -n "$VIRTUAL_ENV"
        # Deactivate if we left the directory that had an auto venv
        if string match -q "$HOME/.virtualenvs/*" "$VIRTUAL_ENV"
            echo "Auto-deactivating virtual environment ..."
            deactivate
        end
    end
end

##
# Command completions
##
complete -c venv -l help -d "Show help"
complete -c venv -a new -d "Create a new virtual environment"
complete -c venv -a activate -d "Select and activate a virtual environment"
complete -c venv -a deactivate -d "Deactivate the current virtual environment"
complete -c venv -a delete -d "Delete a virtual environment"
