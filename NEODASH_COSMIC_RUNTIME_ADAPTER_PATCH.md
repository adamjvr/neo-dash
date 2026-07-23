# NeoDash — COSMIC Runtime Adapter Phase

## Goal

Connect the native libcosmic host to the same renderer-neutral runtime event
stream already used by GTK.

## Added

- `--profile`, repeated `--widget`, and repeated `--widgets-dir` loading
- one `WidgetSession` per configured widget
- runtime-owned execution and refresh timing
- iced subscription-based event delivery
- visible lifecycle/status information per widget
- local `cosmic-winit` runtime testing
- native `cosmic-wayland` compile and Clippy checks

## Apply

```bash
cd ~/GitHub/neo-dash
unzip -o ~/Downloads/neodash_phase_cosmic_runtime_adapter.zip -d .
bash tools/patches/phase_cosmic_runtime_adapter/apply.sh
```

## Validate

```bash
cargo fmt --all
./scripts/check_cosmic_runtime_adapter.sh
```

## Run locally outside COSMIC

```bash
cargo run -p neodash-cosmic --features cosmic-winit -- --profile default
```

No arguments also select the `default` profile.

## Suggested commit

```text
feat(cosmic): consume the shared widget runtime stream

- add profile-aware widget loading to the libcosmic host
- translate RuntimeEvent frames into native COSMIC views
- keep command execution and refresh scheduling in neodash-runtime
- validate both cosmic-winit and cosmic-wayland builds
- document shared GTK and COSMIC runtime parity
```
