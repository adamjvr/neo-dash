#!/usr/bin/env bash
set -euo pipefail

cargo fmt --all -- --check
cargo test -p neodash-cosmic
cargo check -p neodash-runtime
cargo test -p neodash-runtime
cargo clippy -p neodash-runtime -- -D warnings
cargo check -p neodash-cosmic
cargo clippy -p neodash-cosmic -- -D warnings
cargo check -p neodash-cosmic --features cosmic-winit
cargo clippy -p neodash-cosmic --features cosmic-winit -- -D warnings
cargo check -p neodash-cosmic --features cosmic-wayland
cargo clippy -p neodash-cosmic --features cosmic-wayland -- -D warnings

for marker in \
    'cosmic/multi-window' \
    'no_main_window(true)' \
    'window::open' \
    'fn view_window' \
    'Message::WindowClosed' \
    'cosmic::iced::exit()'; do
    if ! grep -q "$marker" crates/neodash-cosmic/Cargo.toml crates/neodash-cosmic/src/main.rs; then
        printf 'error: COSMIC widget-surface marker missing: %s\n' "$marker" >&2
        exit 1
    fi
done

if grep -q 'Native COSMIC runtime host")' crates/neodash-cosmic/src/main.rs; then
    printf 'error: the old combined COSMIC dashboard view is still present\n' >&2
    exit 1
fi

if grep -q 'run_shell_command_once' crates/neodash-cosmic/src/main.rs; then
    printf 'error: COSMIC widget surfaces execute commands directly\n' >&2
    exit 1
fi
