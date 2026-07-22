# NeoDash roadmap

## v0.0.1 — scaffold

- Rust workspace
- Core models
- CLI skeleton
- Shell command runner skeleton
- Example TOML widget

## v0.1 — first visible widget

- GTK4 window
- Shell command source
- Refresh interval
- Text renderer
- Position/size from TOML
- X11 fallback window behavior
- Wayland layer-shell experiment

## v0.2 — actual GeekTool-like use

- GUI inspector
- Drag/resize layout mode
- Save config
- Multiple widgets
- Log widget
- Image widget

## v0.3 — dashboard polish

- Profiles
- Import/export packs
- Web widget via WebKitGTK
- ANSI parser
- Regex filters
- Autostart

## v0.4 — Linux-native built-ins

- CPU/memory/disk/network/battery helpers
- MPRIS now-playing widget
- PipeWire/WirePlumber audio status
- journalctl widget helper
- NetworkManager helper

## v1.0

- Stable widget pack format
- Stable config format
- Real docs
- AppImage/deb/AUR packaging
- Wayland/X11 backend confidence


## Phase 5 update: profile loading started

- Initial `--profile` support in `neodash-app`.
- Example profile at `examples/profiles/default.toml`.
- Relative path resolution for profile widget paths and directories.

## Phase update: shared profile model

Status: complete.

Delivered:

- Shared profile model in `neodash-core`.
- Shared profile path resolution.
- Shared widget directory discovery.
- CLI profile inspection command.
- GTK app now uses the shared profile loader.
- Documentation for the profile model.

Next:

- User config directory discovery.
- Profile lookup by name.
- Duplicate widget ID validation.
- Daemon-owned profile state.
