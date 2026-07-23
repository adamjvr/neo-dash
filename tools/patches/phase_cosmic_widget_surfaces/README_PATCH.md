# NeoDash COSMIC independent widget surfaces

Apply from the NeoDash repository root:

```bash
unzip -o ~/Downloads/neodash_phase_cosmic_widget_surfaces.zip -d .
bash tools/patches/phase_cosmic_widget_surfaces/apply.sh
```

The patch is idempotent and requires the runtime-event-stream and COSMIC
runtime-adapter phases.

Validate:

```bash
cargo fmt --all
./scripts/check_cosmic_widget_surfaces.sh
```

Visual test:

```bash
cargo run -p neodash-cosmic --features cosmic-winit -- \
  --widget examples/widgets/date.toml \
  --widget examples/widgets/uptime.toml \
  --layout-mode \
  --debug-frame
```
