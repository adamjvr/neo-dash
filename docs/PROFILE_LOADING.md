# Profile loading

NeoDash can launch a dashboard from a profile TOML file.

```bash
cargo run -p neodash-app --features gui,x11-desktop -- \
  --profile examples/profiles/default.toml \
  --debug-frame
```

The current implementation is intentionally app-local. The next cleanup is to
move the profile model and path resolution into `neodash-core` so the CLI,
daemon, and GTK app share one parser.

## Format

```toml
id = "default"
name = "Default NeoDash Example Dashboard"
widget_dirs = ["../widgets"]
widgets = []
desktop_hints = true
```

Relative paths are resolved from the profile file's parent directory. The
example profile lives in `examples/profiles`, so `../widgets` points at
`examples/widgets`.

## Current limitations

- No recursive widget directory loading.
- No duplicate widget ID validation yet.
- No themes or per-widget overrides yet.
- No daemon-owned profile state yet.
