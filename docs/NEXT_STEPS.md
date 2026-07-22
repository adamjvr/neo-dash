# Next steps

## Completed baseline

- Initial MPL-2.0 Rust workspace scaffold
- Core widget config model
- Command execution skeleton
- Backend detection skeleton
- Headless check script and CI

## Current iteration: Phase 1 runtime CLI

This iteration gives NeoDash a reusable headless runtime before the first GTK
window exists.

Implemented target behavior:

```bash
cargo run -p neodash-cli -- run --command "date" --interval 1000 --watch
cargo run -p neodash-cli -- run-widget examples/widgets/date.toml
cargo run -p neodash-cli -- run-widget examples/widgets/date.toml --once
```

## Next implementation commit: first GTK window

- Add a real `neodash-app` argument parser
- Accept `--widget examples/widgets/date.toml`
- Create `gtk::Application`
- Create one undecorated window
- Render stdout from the same widget config path
- Refresh on `source.interval_ms`
- Apply initial size from `GeometryConfig`
- Apply basic text/background styling from `StyleConfig`

## Later desktop integration commits

- Wire `gtk4-layer-shell` for supported Wayland sessions
- Add X11 window hints for below/sticky/skip-taskbar behavior
- Add click-through behavior where supported
- Load multiple widgets from `~/.config/neodash/widgets/*.toml`


## Current implementation target: promote profile loading

Profile loading now exists in the GTK app. Next, move `ProfileConfig` into `neodash-core`, add parsing tests, add duplicate widget ID validation, and define the `~/.config/neodash` layout.
