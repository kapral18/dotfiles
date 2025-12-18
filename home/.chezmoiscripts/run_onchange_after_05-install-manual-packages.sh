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

  # Download latest release asset using gh CLI (handles auth automatically)
  if ! gh release download --repo "$github_repo" --pattern "*$asset_pattern" --dir "$temp_dir"; then
    echo "Error: Could not download $app_name from $github_repo" >&2
    return 1
  fi

  # Find the DMG file
  local dmg_file
  dmg_file=$(find "$temp_dir" -name "*$asset_pattern" | head -1)

  if [[ -z "$dmg_file" ]]; then
    echo "Error: Could not find downloaded DMG file" >&2
    return 1
  fi

  # Mount DMG and copy app
  hdiutil attach "$dmg_file" -quiet -nobrowse

  # Find the mounted volume
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

# Squirrel Disk
install_dmg_app "Squirrel Disk" "adileo/squirreldisk" "SquirrelDisk.app"

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
