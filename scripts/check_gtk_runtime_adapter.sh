#!/usr/bin/env bash
set -euo pipefail

cargo fmt --all -- --check
cargo check -p neodash-runtime
cargo test -p neodash-runtime
cargo clippy -p neodash-runtime -- -D warnings
cargo check -p neodash-app --features gui
cargo clippy -p neodash-app --features gui -- -D warnings
cargo check -p neodash-app --features gui,x11-desktop
cargo clippy -p neodash-app --features gui,x11-desktop -- -D warnings

if grep -q 'run_shell_command_once' crates/neodash-app/src/main.rs; then
    printf 'error: GTK still executes commands directly\n' >&2
    exit 1
fi

if grep -q 'refresh_label_once' crates/neodash-app/src/main.rs; then
    printf 'error: GTK-local refresh loop still exists\n' >&2
    exit 1
fi

if grep -q 'neodash-exec' crates/neodash-app/Cargo.toml; then
    printf 'error: neodash-app still depends directly on neodash-exec\n' >&2
    exit 1
fi
