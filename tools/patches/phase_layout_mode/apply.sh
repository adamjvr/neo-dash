#!/usr/bin/env bash
set -euo pipefail

# NeoDash phase: layout/edit mode for movable preview windows
#
# Run from the repository root after extracting this package:
#
#   bash tools/patches/phase_layout_mode/apply.sh

if [[ ! -f Cargo.toml || ! -f crates/neodash-app/src/main.rs || ! -f crates/neodash-cli/src/main.rs ]]; then
  echo "error: run this from the NeoDash repository root" >&2
  exit 1
fi

python3 tools/patches/phase_layout_mode/apply_layout_mode.py

echo
echo "Layout mode phase applied."
echo
echo "Suggested test gate:"
echo "  cargo fmt --all"
echo "  ./scripts/check_headless.sh"
echo "  cargo check -p neodash-app --features gui"
echo "  cargo check -p neodash-app --features gui,x11-desktop"
echo
echo "Manual tests:"
echo "  cargo run -p neodash-cli -- config-init --force"
echo "  cargo run -p neodash-app --features gui,x11-desktop -- --profile default --layout-mode --debug-frame"
echo "  cargo run -p neodash-app --features gui,x11-desktop -- --profile default --no-desktop-hints --decorated --resizable --debug-frame"
echo "  cargo run -p neodash-app --features gui,x11-desktop -- --profile default --debug-frame"
