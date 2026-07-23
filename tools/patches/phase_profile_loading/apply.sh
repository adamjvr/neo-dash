#!/usr/bin/env bash
set -euo pipefail
if [[ ! -f Cargo.toml || ! -d crates/neodash-app ]]; then
  echo "error: run this from the NeoDash repository root" >&2
  exit 1
fi
python3 tools/patches/phase_profile_loading/apply_profile_loading.py
