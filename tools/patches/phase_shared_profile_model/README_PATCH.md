# NeoDash phase package: shared profile model

This package is intended to be extracted into the root of the `neo-dash` repository.

It adds the next phase after GTK profile loading:

- moves profile parsing/path-resolution into `neodash-core`
- removes app-local profile parsing from `neodash-app`
- adds shared widget-directory discovery in core
- adds `neodash profile-info <PATH>` to the CLI
- adds profile model documentation

## Apply

From the repository root:

```bash
unzip -o neodash_phase_shared_profile_model.zip -d .
bash tools/patches/phase_shared_profile_model/apply.sh
```

## Test

```bash
cargo fmt --all
./scripts/check_headless.sh
cargo check -p neodash-app --features gui
cargo check -p neodash-app --features gui,x11-desktop
cargo run -p neodash-cli -- profile-info examples/profiles/default.toml
cargo run -p neodash-app --features gui,x11-desktop -- --profile examples/profiles/default.toml --debug-frame
```

## Commit

```bash
git add Cargo.lock README.md docs/NEXT_STEPS.md docs/ROADMAP.md docs/PROFILE_LOADING.md docs/PROFILE_MODEL.md crates/neodash-core/src/lib.rs crates/neodash-core/src/profile.rs crates/neodash-app/Cargo.toml crates/neodash-app/src/main.rs crates/neodash-cli/src/main.rs
git commit -m "Move profile loading into neodash-core"
git push origin main
```
