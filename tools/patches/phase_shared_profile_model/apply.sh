#!/usr/bin/env bash
set -euo pipefail

# NeoDash phase: shared profile model
#
# Run from the repository root after extracting this package:
#
#   bash tools/patches/phase_shared_profile_model/apply.sh

if [[ ! -f Cargo.toml || ! -d crates/neodash-core || ! -d crates/neodash-app ]]; then
  echo "error: run this from the NeoDash repository root" >&2
  exit 1
fi

python3 tools/patches/phase_shared_profile_model/apply_shared_profile_model.py

echo
echo "Shared profile model patch applied."
echo
echo "Suggested test gate:"
echo "  cargo fmt --all"
echo "  ./scripts/check_headless.sh"
echo "  cargo check -p neodash-app --features gui"
echo "  cargo check -p neodash-app --features gui,x11-desktop"
echo
echo "Manual profile tests:"
echo "  cargo run -p neodash-cli -- profile-info examples/profiles/default.toml"
echo "  cargo run -p neodash-app --features gui,x11-desktop -- --profile examples/profiles/default.toml --debug-frame"
