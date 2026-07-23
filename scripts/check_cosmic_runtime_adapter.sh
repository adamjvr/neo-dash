#!/usr/bin/env bash
set -euo pipefail

cargo fmt --all -- --check
cargo check -p neodash-runtime
cargo test -p neodash-runtime
cargo clippy -p neodash-runtime -- -D warnings
cargo check -p neodash-cosmic
cargo clippy -p neodash-cosmic -- -D warnings
cargo check -p neodash-cosmic --features cosmic-winit
cargo clippy -p neodash-cosmic --features cosmic-winit -- -D warnings
cargo check -p neodash-cosmic --features cosmic-wayland
cargo clippy -p neodash-cosmic --features cosmic-wayland -- -D warnings

if grep -q 'run_shell_command_once' crates/neodash-cosmic/src/main.rs; then
    printf 'error: COSMIC still executes commands directly\n' >&2
    exit 1
fi

if grep -q 'neodash-exec' crates/neodash-cosmic/Cargo.toml; then
    printf 'error: neodash-cosmic depends directly on neodash-exec\n' >&2
    exit 1
fi

for marker in 'spawn_widget_runtime' 'RuntimeEvent' 'Message::PollRuntime'; do
    if ! grep -q "$marker" crates/neodash-cosmic/src/main.rs; then
        printf 'error: COSMIC runtime adapter marker missing: %s\n' "$marker" >&2
        exit 1
    fi
done
