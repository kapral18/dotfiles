#!/usr/bin/env bash
# Install Cursor's agent-cli-local flavor (cursor-agent-local), pinned to a cursor-agent version.
#
# Usage: install.sh <cursor-agent-version>
#
# cursor-agent (cloud build) hard-rejects --base-url/--local-agent-api-key ("can only be used with
# agent-cli-local"); only the sibling agent-cli-local distribution accepts an OpenAI-compatible or
# Anthropic Messages provider. Both flavors ship as per-version tarballs in Cursor's public S3
# bucket, so the flavor is installed in lockstep with the cursor-agent on PATH. The layout mirrors
# the product's own installer (install-core-posix in the dist bundle): versioned directories under
# ~/.local/share/cursor-agent-local/versions/ with bin symlinks at ~/.local/bin/cursor-agent-local
# and agent-local. Idempotent: an existing version directory is reused as-is.
set -euo pipefail

version="${1:-}"
if [[ -z "$version" ]]; then
  echo "Usage: install.sh <cursor-agent-version>" >&2
  exit 2
fi

case "$(uname -s)" in
  Darwin) os="darwin" ;;
  Linux) os="linux" ;;
  *)
    echo "Error: unsupported OS: $(uname -s)" >&2
    exit 1
    ;;
esac
case "$(uname -m)" in
  arm64 | aarch64) arch="arm64" ;;
  x86_64) arch="x64" ;;
  *)
    echo "Error: unsupported arch: $(uname -m)" >&2
    exit 1
    ;;
esac

root="$HOME/.local/share/cursor-agent-local"
dest="$root/versions/$version"
bin="$HOME/.local/bin"

if [[ ! -x "$dest/cursor-agent-local" ]]; then
  # Trust note: Cursor publishes no checksum/signature for these tarballs
  # (probed .sha256/.sha256sum/.checksums.txt on the bucket -> 403), so the
  # control is HTTPS to the pinned anysphere-binaries S3 URL plus the
  # version-lockstep with the cursor-agent on PATH.
  url="https://anysphere-binaries.s3.amazonaws.com/lab/$version/$os/$arch/agent-cli-local-package.tar.gz"
  # Unique staging per run: the onchange hook and ,cursor-openrouter's
  # self-heal can race on first launch, and a shared staging dir would let
  # one racer's rm/extract clobber the other's.
  mkdir -p "$root/versions"
  staging="$(mktemp -d "$root/versions/.$version.XXXXXX")"
  echo "Installing agent-cli-local $version ($os/$arch)..." >&2
  curl -fSL "$url" | tar --strip-components=1 -xzf - -C "$staging"
  if [[ ! -x "$dest/cursor-agent-local" ]]; then
    rm -rf "$dest"
    mv "$staging" "$dest"
  else
    rm -rf "$staging"
  fi
fi

mkdir -p "$bin"
ln -sfn "$dest/cursor-agent-local" "$bin/cursor-agent-local"
ln -sfn "$dest/cursor-agent-local" "$bin/agent-local"
echo "cursor-agent-local $version ready at $dest"
