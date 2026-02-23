#!/usr/bin/env bash
set -euo pipefail

keep_count="$(tmux show-option -gqv '@resurrect_keep_sessions' || true)"
if [[ -z "${keep_count}" ]]; then
  keep_count="5"
fi

if ! [[ "${keep_count}" =~ ^[0-9]+$ ]]; then
  exit 0
fi

resurrect_file_path="${1:-}"

if [[ -z "${resurrect_file_path}" ]]; then
  resurrect_dir_option="$(tmux show-option -gqv '@resurrect-dir' || true)"
  if [[ -n "${resurrect_dir_option}" ]]; then
    resurrect_dir="${resurrect_dir_option/#\~/$HOME}"
    resurrect_dir="${resurrect_dir//\$HOME/$HOME}"
    resurrect_dir="${resurrect_dir//\$HOSTNAME/$(hostname)}"
  elif [[ -d "$HOME/.tmux/resurrect" ]]; then
    resurrect_dir="$HOME/.tmux/resurrect"
  else
    resurrect_dir="${XDG_DATA_HOME:-$HOME/.local/share}/tmux/resurrect"
  fi

  last_link="${resurrect_dir}/last"
  if [[ ! -e "${last_link}" ]]; then
    exit 0
  fi

  if [[ -L "${last_link}" ]]; then
    target="$(readlink "${last_link}" || true)"
    if [[ -z "${target}" ]]; then
      exit 0
    fi
    resurrect_file_path="${resurrect_dir}/${target}"
  else
    resurrect_file_path="${last_link}"
  fi
fi

if [[ ! -f "${resurrect_file_path}" ]]; then
  exit 0
fi

file_session_count="$(
  awk -F $'\t' '$1 == "pane" { print $2 }' "${resurrect_file_path}" |
    awk '!seen[$0]++ { c++ } END { print c + 0 }'
)"

# Prefer a keep list captured during the last save (so pre-restore can be fast and correct).
session_keep_list="$(
  awk -F $'\t' '
    $1 == "#k18_keep_sessions" {
      for (i = 2; i <= NF; i++) {
        if ($i != "") print $i;
      }
      exit
    }
  ' "${resurrect_file_path}" |
    head -n "${keep_count}"
)"

if [[ -z "${session_keep_list}" ]]; then
  tmux_session_count="$(tmux list-sessions 2>/dev/null | wc -l | tr -d ' ')"

  if [[ -n "${tmux_session_count}" ]] && [[ "${tmux_session_count}" =~ ^[0-9]+$ ]] && [[ "${tmux_session_count}" -ge "${file_session_count}" ]] && [[ "${file_session_count}" -gt 0 ]]; then
    # Likely running as a post-save hook (tmux state matches what was saved).
    session_keep_list="$(
      tmux list-sessions -F $'#{session_name}\t#{session_activity}' 2>/dev/null |
        sort -nr -k2,2 -t $'\t' |
        head -n "${keep_count}" |
        cut -f1
    )"
  else
    # Likely running as a pre-restore hook (tmux state is minimal).
    # Best-effort: prioritize the active + alternate sessions at save time, then fill from file order.
    state_sessions="$(
      awk -F $'\t' '
        $1 == "state" {
          if ($2 != "") print $2;
          if ($3 != "") print $3;
          exit
        }
      ' "${resurrect_file_path}" |
        awk '!seen[$0]++'
    )"
    file_sessions="$(
      awk -F $'\t' '$1 == "pane" { print $2 }' "${resurrect_file_path}" |
        awk '!seen[$0]++'
    )"

    session_keep_list="$(
      printf '%s\n%s\n' "${state_sessions}" "${file_sessions}" |
        awk '!seen[$0]++' |
        head -n "${keep_count}"
    )"
  fi
fi

if [[ -z "${session_keep_list}" ]]; then
  exit 0
fi

keep_file="$(mktemp "${resurrect_file_path}.k18.keep.XXXXXX")"
printf '%s\n' "${session_keep_list}" > "${keep_file}"

tmp_file="$(mktemp "${resurrect_file_path}.k18.XXXXXX")"
keep_sessions_line="#k18_keep_sessions"
while IFS= read -r name; do
  [[ -z "${name}" ]] && continue
  keep_sessions_line+=$'\t'"${name}"
done < "${keep_file}"

awk -v keep_file="${keep_file}" -v keep_count="${keep_count}" -v keep_sessions_line="${keep_sessions_line}" '
BEGIN {
  FS = "\t";
  OFS = "\t";
  keep_order_count = 0;
  while ((getline name < keep_file) > 0) {
    if (name != "") {
      keep[name] = 1;
      keep_order[++keep_order_count] = name;
    }
  }
  close(keep_file);

  # Place k18 metadata at the top for the pre-restore hook.
  print "#k18_keep_count", keep_count;
  print keep_sessions_line;
}

$0 == "" { print; next }

$0 ~ /^#k18_/ { next }
$0 ~ /^#/ { print; next }

$1 == "pane" { if (keep[$2]) print; next }
$1 == "window" { if (keep[$2]) print; next }
$1 == "grouped_session" { if (keep[$2] && keep[$3]) print; next }
$1 == "state" { next }

{ next }

END {
  # Normalize the active/alternate sessions to ones we actually keep.
  active = keep_order[1];
  alt = keep_order[2];
  if (active == "") active = alt;
  if (alt == "") alt = active;
  if (active != "" && alt != "") {
    print "state", active, alt;
  }
}
' "${resurrect_file_path}" > "${tmp_file}"
rm -f "${keep_file}"
mv "${tmp_file}" "${resurrect_file_path}"
