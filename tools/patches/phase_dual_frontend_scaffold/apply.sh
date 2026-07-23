#!/usr/bin/env bash
set -euo pipefail

# NeoDash phase: dual GTK + native COSMIC frontend scaffold
# Run from the repository root after extracting this package.

if [[ ! -f Cargo.toml || ! -f crates/neodash-platform/src/lib.rs || ! -f crates/neodash-app/Cargo.toml ]]; then
  echo "error: run this from the NeoDash repository root" >&2
  exit 1
fi

python3 tools/patches/phase_dual_frontend_scaffold/apply_dual_frontend_scaffold.py

echo
echo "Dual frontend scaffold applied."
echo
echo "Install the current libcosmic build prerequisites if needed:"
echo "  sudo apt install cmake libexpat1-dev libfontconfig-dev libfreetype-dev libwayland-dev libxkbcommon-dev pkg-config"
echo
echo "Validation gate:"
echo "  cargo fmt --all"
echo "  ./scripts/check_headless.sh"
echo "  ./scripts/check_frontends.sh"
echo "  cargo test -p neodash-platform"
echo
echo "Local visual tests on the current non-COSMIC desktop:"
echo "  cargo run -p neodash-app --features gui,x11-desktop -- --profile default --layout-mode --debug-frame"
echo "  cargo run -p neodash-cosmic --features cosmic-winit"
echo
echo "Native COSMIC target compile test:"
echo "  cargo check -p neodash-cosmic --features cosmic-wayland"
echo
echo "Note: Cargo.lock will change the first time libcosmic is resolved; commit it with the phase."
