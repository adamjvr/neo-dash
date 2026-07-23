#!/usr/bin/env bash
set -euo pipefail

# NeoDash repair: fix Rust raw-string delimiters in config-init starter TOML.
#
# Run from the repository root:
#
#   bash tools/patches/phase_config_directory_fix/apply.sh

if [[ ! -f Cargo.toml || ! -f crates/neodash-cli/src/main.rs ]]; then
  echo "error: run this from the NeoDash repository root" >&2
  exit 1
fi

python3 tools/patches/phase_config_directory_fix/apply_config_directory_fix.py

echo
echo "Config directory raw-string repair applied."
echo
echo "Run:"
echo "  cargo fmt --all"
echo "  ./scripts/check_headless.sh"
echo "  cargo check -p neodash-app --features gui"
echo "  cargo check -p neodash-app --features gui,x11-desktop"
echo "  cargo run -p neodash-cli -- config-init --force"
echo "  cargo run -p neodash-cli -- profile-check default"
echo "  cargo run -p neodash-app --features gui,x11-desktop -- --profile default --debug-frame"
