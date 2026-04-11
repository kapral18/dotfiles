#!/bin/bash

# crontab contents hash: {{ include "crontab" | sha256sum }}

set -euo pipefail

chezmoi_source="$(chezmoi source-path)"
crontab "${chezmoi_source}/crontab"
