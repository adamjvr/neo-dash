# NeoDash profile loading phase package

Extract this zip into the repo root, then run:

```bash
bash tools/patches/phase_profile_loading/apply.sh
cargo fmt --all
./scripts/check_headless.sh
cargo check -p neodash-app --features gui
cargo check -p neodash-app --features gui,x11-desktop
cargo run -p neodash-app --features gui,x11-desktop -- --profile examples/profiles/default.toml --debug-frame
```

Commit:

```bash
git add Cargo.lock README.md docs/NEXT_STEPS.md docs/ROADMAP.md docs/PROFILE_LOADING.md crates/neodash-app/Cargo.toml crates/neodash-app/src/main.rs examples/profiles/default.toml
git commit -m "Add profile loading for GTK dashboard preview"
git push origin main
```
