#!/usr/bin/env bash
set -euo pipefail

if [[ ! -f Cargo.toml || ! -d crates/neodash-core || ! -d crates/neodash-cli || ! -d crates/neodash-app ]]; then
  echo "error: run this from the NeoDash repository root" >&2
  exit 1
fi

python3 tools/patches/phase_profile_validation/apply_profile_validation.py

echo
echo "Profile validation patch applied."
echo
echo "Suggested test gate:"
echo "  cargo fmt --all"
echo "  ./scripts/check_headless.sh"
echo "  cargo check -p neodash-app --features gui"
echo "  cargo check -p neodash-app --features gui,x11-desktop"
echo
echo "Manual validation test:"
echo "  cargo run -p neodash-cli -- profile-check examples/profiles/default.toml"
echo "  cargo run -p neodash-cli -- profile-info examples/profiles/default.toml"
echo "  cargo run -p neodash-app --features gui,x11-desktop -- --profile examples/profiles/default.toml --debug-frame"
