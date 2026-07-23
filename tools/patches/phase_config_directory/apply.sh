#!/usr/bin/env bash
set -euo pipefail

# NeoDash phase: config directory support
#
# Run from the repository root after extracting this package:
#
#   bash tools/patches/phase_config_directory/apply.sh

if [[ ! -f Cargo.toml || ! -d crates/neodash-core || ! -d crates/neodash-cli || ! -d crates/neodash-app ]]; then
  echo "error: run this from the NeoDash repository root" >&2
  exit 1
fi

python3 tools/patches/phase_config_directory/apply_config_directory.py

echo
echo "Config directory phase applied."
echo
echo "Suggested test gate:"
echo "  cargo fmt --all"
echo "  ./scripts/check_headless.sh"
echo "  cargo check -p neodash-app --features gui"
echo "  cargo check -p neodash-app --features gui,x11-desktop"
echo
echo "Manual config tests:"
echo "  cargo run -p neodash-cli -- config-dir"
echo "  cargo run -p neodash-cli -- config-init --force"
echo "  cargo run -p neodash-cli -- profile-info default"
echo "  cargo run -p neodash-cli -- profile-check default"
echo "  cargo run -p neodash-app --features gui,x11-desktop -- --profile default --debug-frame"
