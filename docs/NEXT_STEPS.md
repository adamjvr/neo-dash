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

## Current implementation target: user config discovery

Profile parsing is now shared through `neodash-core`. The next runtime milestone
is user config discovery.

Target layout:

```text
~/.config/neodash/
  profiles/
    default.toml
  widgets/
    date.toml
    uptime.toml
  themes/
    default.toml
```

Target commands:

```bash
neodash profile-info default
neodash-app --profile default
```

Implementation notes:

- Use the `directories` crate already present in workspace dependencies.
- Keep explicit file paths working.
- Add a resolver that treats bare names as profile IDs under the config dir.
- Add tests before moving more runtime ownership into the daemon.


## Current implementation target: daemon-owned profile runtime

Profile parsing and validation are now shared in `neodash-core`. The next major phase is to make the daemon own a loaded, validated profile instead of keeping all runtime state inside `neodash-app`.

Pre-daemon checks:

```bash
cargo run -p neodash-cli -- profile-check examples/profiles/default.toml
cargo run -p neodash-app --features gui,x11-desktop -- --profile examples/profiles/default.toml --debug-frame
```


## Current implementation target: daemon-owned runtime

Config directory support is now the bridge between repo examples and a real
installed app workflow. The next major phase should move profile ownership into
`neodash-daemon`.

Current app-style flow:

```bash
cargo run -p neodash-cli -- config-init --force
cargo run -p neodash-cli -- profile-check default
cargo run -p neodash-app --features gui,x11-desktop -- --profile default --debug-frame
```

Next daemon targets:

- Define daemon command interface.
- Add `neodash daemon start`.
- Add `neodash daemon status`.
- Make the daemon load a profile by name.
- Make the daemon own refresh scheduling.
- Keep GTK as a viewer/editor instead of the sole runtime owner.
