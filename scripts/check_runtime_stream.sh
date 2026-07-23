#!/usr/bin/env bash
set -euo pipefail

cargo fmt --all -- --check
cargo check -p neodash-runtime
cargo test -p neodash-runtime
cargo clippy -p neodash-runtime -- -D warnings
cargo check -p neodash-daemon
cargo clippy -p neodash-daemon -- -D warnings
