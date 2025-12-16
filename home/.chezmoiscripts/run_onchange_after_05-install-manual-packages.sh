#!/usr/bin/env bash

set -euo pipefail

mkdir -p ~/.local/bin

# -----------------------------------------------
# Function to download and install DMG-based macOS apps from GitHub releases
# -----------------------------------------------

# Usage: install_dmg_app "AppName" "owner/repo" "app.bundle.name" [asset-pattern]
# Example: install_dmg_app "FluidVoice" "altic-dev/FluidVoice" "FluidVoice.app"
install_dmg_app() {
  local app_name="$1"
  local github_repo="$2"
  local app_bundle="$3"
  local asset_pattern="${4:-.dmg}"

  local app_path="/Applications/$app_bundle"

  if [[ -d "$app_path" ]]; then
    echo "$app_name is already installed"
    return 0
  fi

  echo "Installing $app_name..."
  local temp_dir
  temp_dir=$(mktemp -d)
  trap "rm -rf $temp_dir" EXIT

  # Get latest release download URL
  local download_url
  download_url=$(curl -s "https://api.github.com/repos/$github_repo/releases/latest" |
    grep -o "\"browser_download_url\": \"[^\"]*$asset_pattern\"" |
    cut -d'"' -f4 | head -1)

  if [[ -z "$download_url" ]]; then
    echo "Error: Could not find $app_name DMG download URL" >&2
    return 1
  fi

  local dmg_file="$temp_dir/$app_name.dmg"
  curl -L "$download_url" -o "$dmg_file"

  # Mount DMG and copy app
  hdiutil attach "$dmg_file" -quiet -nobrowse

  # Find the mounted volume (try multiple patterns)
  local volume=""
  for vol in /Volumes/*; do
    if [[ -d "$vol/$app_bundle" ]]; then
      volume="$vol"
      break
    fi
  done

  if [[ -z "$volume" ]]; then
    echo "Error: Could not find $app_bundle on mounted volume" >&2
    hdiutil detach /Volumes/* -quiet 2>/dev/null || true
    return 1
  fi

  cp -r "$volume/$app_bundle" /Applications/
  hdiutil detach "$volume" -quiet

  echo "$app_name installed successfully"
}

# -----------------------------------------------
# DMG-based macOS apps
# -----------------------------------------------

# FluidVoice
install_dmg_app "FluidVoice" "altic-dev/FluidVoice" "FluidVoice.app"

# Add more DMG apps here:
# install_dmg_app "AppName" "owner/repo" "AppName.app"

# -----------------------------------------------
# Install command-line tools
# -----------------------------------------------

# YtSurf
curl -o ~/.local/bin/ytsurf https://raw.githubusercontent.com/kapral18/ytsurf/reduce-deps/ytsurf.sh
chmod +x ~/.local/bin/ytsurf

# amp
if ! command -v amp &>/dev/null; then
  curl -fsSL https://ampcode.com/install.sh | bash
fi
