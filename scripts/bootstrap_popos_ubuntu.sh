#!/usr/bin/env bash
set -euo pipefail

# NeoDash dev bootstrap for Ubuntu / Pop!_OS style systems.
# This intentionally installs the boring native dependencies first. Rust comes
# from rustup because distro Rust packages are often stale for GUI crates.

sudo apt update
sudo apt install -y \
  build-essential \
  curl \
  git \
  pkg-config \
  libgtk-4-dev \
  libadwaita-1-dev \
  libwebkitgtk-6.0-dev \
  libsqlite3-dev

if ! command -v rustup >/dev/null 2>&1; then
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
fi

# shellcheck disable=SC1090
source "$HOME/.cargo/env"
rustup default stable

cargo check
