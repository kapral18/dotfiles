#!/usr/bin/env bash
set -euo pipefail

PATH="$HOME/bin:$PATH"
trap 'exit 0' INT HUP TERM

if ! command -v ,gh-tfork > /dev/null 2>&1; then
  printf "\033[38;5;203mMissing:\033[0m ,gh-tfork (is chezmoi applied?)\n" >&2
  printf "\033[38;5;244mpress any key to close\033[0m" >&2
  read -rsn 1 < /dev/tty || true
  exit 127
fi

prompt_prefix="\033[38;5;111m\033[0m \033[38;5;244mrepo\033[0m \033[38;5;244m(owner/repo)\033[0m \033[38;5;244m>\033[0m "
hint="\033[38;5;240m(esc to cancel)\033[0m"

esc="$(printf '\033')"
ctrl_c="$(printf '\003')"
cr="$(printf '\r')"
nl="$(printf '\n')"
bs="$(printf '\177')"

buf=""
printf "%b%b" "$prompt_prefix" "$hint"
printf "\r%b" "$prompt_prefix"

while IFS= read -rsn 1 ch < /dev/tty; do
  case "$ch" in
    "$ctrl_c" | "$esc")
      exit 0
      ;;
    "$cr" | "$nl")
      break
      ;;
    "$bs" | $'\b')
      if [ -n "$buf" ]; then
        buf="${buf%?}"
      fi
      ;;
    *)
      buf+="$ch"
      ;;
  esac
  printf "\r%b%s\033[K" "$prompt_prefix" "$buf"
done

# trim whitespace
repo_spec="$buf"
repo_spec="${repo_spec#"${repo_spec%%[![:space:]]*}"}"
repo_spec="${repo_spec%"${repo_spec##*[![:space:]]}"}"
if [ -z "$repo_spec" ]; then
  exit 0
fi

printf "\n"
if ,gh-tfork "$repo_spec"; then
  exit 0
fi

printf "\n\033[38;5;203mfailed\033[0m (press any key to close)" >&2
read -rsn 1 < /dev/tty || true
