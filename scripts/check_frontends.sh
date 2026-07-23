#!/usr/bin/env bash
set -euo pipefail

# Checks both NeoDash frontend families without requiring the current login
# session to be COSMIC.

cargo check -p neodash-app --features gui
cargo check -p neodash-app --features gui,x11-desktop
cargo check -p neodash-cosmic
cargo check -p neodash-cosmic --features cosmic-winit
cargo check -p neodash-cosmic --features cosmic-wayland
