# NeoDash phase package: profile validation

This package is intended to be extracted into the root of the `neo-dash` repository.

It adds the next phase:

- shared profile validation in `neodash-core`,
- duplicate widget ID detection,
- missing widget file and directory checks,
- widget TOML parse checks,
- shell widget command validation,
- current-runtime rejection of enabled non-shell widgets,
- `neodash profile-check <PROFILE>` CLI command,
- GTK app validation before launching a profile,
- profile validation documentation.

## Apply

From the repository root:

```bash
unzip -o neodash_phase_profile_validation.zip -d .
bash tools/patches/phase_profile_validation/apply.sh
```

## Test

```bash
cargo fmt --all
./scripts/check_headless.sh
cargo check -p neodash-app --features gui
cargo check -p neodash-app --features gui,x11-desktop
cargo run -p neodash-cli -- profile-check examples/profiles/default.toml
cargo run -p neodash-cli -- profile-info examples/profiles/default.toml
cargo run -p neodash-app --features gui,x11-desktop -- --profile examples/profiles/default.toml --debug-frame
```

## Commit

```bash
git add README.md docs/NEXT_STEPS.md docs/ROADMAP.md docs/PROFILE_MODEL.md docs/PROFILE_VALIDATION.md crates/neodash-core/src/profile.rs crates/neodash-cli/src/main.rs crates/neodash-app/src/main.rs

git commit -m "Add shared profile validation"

git push origin main
```
