# NeoDash phase package: layout mode

Extract this package into the root of the `neo-dash` repository.

This phase adds:

- `neodash-app --layout-mode`
- `neodash-app --no-desktop-hints`
- normal decorated/resizable movable widget windows for layout/debugging
- slightly safer starter widget spacing
- layout mode documentation

## Apply

```bash
cd ~/GitHub/neo-dash
unzip -o neodash_phase_layout_mode.zip -d .
bash tools/patches/phase_layout_mode/apply.sh
```

## Test

```bash
cargo fmt --all
./scripts/check_headless.sh
cargo check -p neodash-app --features gui
cargo check -p neodash-app --features gui,x11-desktop

cargo run -p neodash-cli -- config-init --force

cargo run -p neodash-app --features gui,x11-desktop -- \
  --profile default \
  --layout-mode \
  --debug-frame

cargo run -p neodash-app --features gui,x11-desktop -- \
  --profile default
```

## Commit

```bash
git add README.md docs/NEXT_STEPS.md docs/ROADMAP.md docs/LAYOUT_MODE.md crates/neodash-app/src/main.rs crates/neodash-cli/src/main.rs examples/widgets/uptime.toml
git commit -m "Add layout mode for movable widget windows"
git push origin main
```
