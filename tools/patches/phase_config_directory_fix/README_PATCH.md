# NeoDash config directory repair

This fixes the Rust raw string delimiter bug in the config directory phase.

The generated starter widget TOML contains color values like:

```toml
foreground = "#eeeeee"
background = "#00000088"
```

Those prematurely closed Rust strings written as `r#"..."#`. This repair changes the widget TOML constants to `r##"..."##`.

## Apply

```bash
cd ~/GitHub/neo-dash
unzip -o neodash_phase_config_directory_fix.zip -d .
bash tools/patches/phase_config_directory_fix/apply.sh
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
git add crates/neodash-cli/src/main.rs
git commit -m "Fix config-init starter widget raw strings"
git push origin main
```
