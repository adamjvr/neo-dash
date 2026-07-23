#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

python3 tools/patches/phase_cosmic_wgpu_hotfix/apply_cosmic_wgpu_hotfix.py
cargo fmt --all

cat <<'EOF'

COSMIC WGPU hotfix applied.

Validate:
  cargo check -p neodash-cosmic --features cosmic-winit
  cargo run -p neodash-cosmic --features cosmic-winit
  cargo check -p neodash-cosmic --features cosmic-wayland
  cargo clippy -p neodash-cosmic --features cosmic-winit -- -D warnings
EOF
