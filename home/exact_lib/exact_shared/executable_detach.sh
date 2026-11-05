#!/usr/bin/env bash
# Run "$@" in a new session. Closing a herdr popup sends HUP, TERM, then KILL to
# every process in the popup's session, so work that must outlive the picker
# has to leave it; nohup and disown do not.
exec perl -MPOSIX=setsid -e 'setsid() != -1 or die "detach: setsid: $!\n"; exec { $ARGV[0] } @ARGV or die "detach: $ARGV[0]: $!\n"' "$@"
