# Contributing to NeoDash

NeoDash is MPL-2.0 licensed and Rust-first.

## Ground rules

- Keep core crates toolkit-free and mostly pure Rust.
- Keep Linux desktop integration isolated behind `neodash-platform` and `neodash-app`.
- Do not copy GPL code into the tree unless the project license is intentionally revisited.
- Add `SPDX-License-Identifier: MPL-2.0` to new Rust source files.
- Prefer small crates with boring responsibilities over one giant app crate.

## Local checks

```bash
cargo fmt
cargo clippy --workspace --all-targets
cargo test --workspace
cargo check --workspace
```
