# NeoDash phase package: config directory support

Extract this package into the root of the `neo-dash` repository.

This phase adds:

- `neodash-core` config path resolution
- `NEODASH_CONFIG_DIR` override support
- XDG-style default config root resolution
- bare profile-name resolution such as `default`
- `neodash config-dir`
- `neodash config-init`
- `neodash-app --profile default`
- config directory documentation

## Apply

```bash
cd ~/GitHub/neo-dash
unzip -o neodash_phase_config_directory.zip -d .
bash tools/patches/phase_config_directory/apply.sh
```

## Test

```bash
cargo fmt --all
./scripts/check_headless.sh
cargo check -p neodash-app --features gui
cargo check -p neodash-app --features gui,x11-desktop

cargo run -p neodash-cli -- config-dir
cargo run -p neodash-cli -- config-init --force
cargo run -p neodash-cli -- profile-info default
cargo run -p neodash-cli -- profile-check default

cargo run -p neodash-app --features gui,x11-desktop -- --profile default --debug-frame
```

## Commit

```bash
git add README.md docs/NEXT_STEPS.md docs/ROADMAP.md docs/CONFIG_DIRECTORY.md crates/neodash-core/src/lib.rs crates/neodash-core/src/config_paths.rs crates/neodash-cli/src/main.rs crates/neodash-app/src/main.rs
git commit -m "Add user config directory support"
git push origin main
```
