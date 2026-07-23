# NeoDash — Runtime Event Stream Phase

## Goal

Create the shared execution boundary required by both the GTK and native COSMIC
frontends. Widget command execution, refresh timing, cancellation, and normalized
text frames now live in `neodash-runtime`, not in a toolkit.

## Added

- `RuntimeFrame`
- `RuntimeEvent`
- `WidgetRuntimeHandle`
- `execute_widget_frame()`
- `spawn_widget_runtime()`
- daemon CLI smoke-test path
- runtime-specific validation script
- architecture notes for the following frontend-adapter phase

## Corrected packaging

This archive extracts directly into the repository root. The apply script uses
its own absolute path, so it no longer depends on the patch files already being
under `tools/patches` before it starts.

The daemon patch also adds `clap.workspace = true`, which is required by the new
`#[derive(Parser)]` command-line interface.

## Smoke test

```bash
cargo run -p neodash-daemon -- \
  --widget examples/widgets/date.toml \
  --frames 3
```

## Suggested commit

```text
feat(runtime): add daemon-owned widget event stream

- add renderer-neutral runtime frames and lifecycle events
- move refresh timing into cancellable widget workers
- add daemon CLI smoke testing for widget streams
- keep GTK and libcosmic dependencies out of the runtime crate
- add runtime validation and architecture documentation
```
