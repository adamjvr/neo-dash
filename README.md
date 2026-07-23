# NeoDash

**NeoDash — GeekTool reborn for Linux.**

NeoDash is a Rust-native Linux desktop widget system inspired by GeekTool. The goal is to let Linux users pin live command output, logs, images, generated HTML, web views, and custom dashboards directly onto the desktop without dragging in Electron, Node, Python, or a pile of glue scripts.

This repository is the **v0.1 starter project**. It is structured as a real Rust workspace that can grow into a daemon, CLI, and GTK4/libadwaita desktop editor while keeping the core logic pure Rust.

## Why NeoDash exists

GeekTool had the right idea: small live objects on the desktop, powered by shell commands, log files, images, and web content. Linux has pieces of that world—Conky, Eww, Waybar, Plasma widgets—but NeoDash aims for a GeekTool-style visual desktop workflow with modern Linux display-server reality baked in from day one.

## COSMIC / Pop!_OS direction

NeoDash is intentionally aligned with the Rust-heavy direction of COSMIC and modern Pop!_OS. The core crates are Rust. The CLI and daemon are Rust. The GUI code will be Rust. The only non-Rust part of the application stack is the unavoidable Linux desktop integration layer: GTK4, libadwaita, Wayland/layer-shell, X11, Cairo/Pango/GLib, and eventually WebKitGTK for web widgets.

In other words:

```text
Rust-native, not Electron.
Rust app logic, not Python scripts duct-taped together.
Native Linux toolkit bindings only where the desktop requires them.
```

## License

NeoDash is licensed under the **Mozilla Public License 2.0**.

SPDX identifier:

```text
MPL-2.0
```

The MPL is a strong fit here because it keeps NeoDash source files open while still being less viral than GPL for surrounding integrations, distro packaging, plugins, and downstream experiments.

## Core idea

NeoDash uses a three-part object model:

```text
Source / Measure
  shell command, log file, image path, URL, HTTP/JSON, DBus, sensor

Transform
  ANSI parser, regex filters, regex replace, JSON path, templates

Renderer / Meter
  text, terminal text, image, web view, graph, progress bar, table
```

That gives us simple GeekTool behavior first while leaving room for Rainmeter/Conky/Eww/Waybar-style power later.

## v0.1 target

First proof:

```bash
neodash run --command "date" --interval 1000 --watch
```

Then the first real graphical milestone:

```text
Put that command output inside a borderless desktop widget window.
```

## Planned widget types

| Widget | Purpose |
|---|---|
| Shell | Run a command every N milliseconds and display stdout |
| Log | Tail a file, survive rotation, filter lines, color output |
| Image | Show local image, generated PNG, slideshow, or remote image |
| Web | Show URL, local HTML, or command-generated HTML |
| Text | Static labels, section headers, notes, helper text |

## Display backends

NeoDash is designed around multiple platform backends:

| Backend | Purpose |
|---|---|
| Wayland layer-shell | Proper desktop-layer widgets on supported compositors |
| COSMIC Wayland | Treated as a first-class Wayland/layer-shell target |
| X11 fallback | Sticky, undecorated, below-window widgets on X11 desktops |
| GNOME Wayland fallback | Degraded mode first, shell extension bridge later |

## Current scaffold status

Implemented in this starter:

- Rust workspace layout
- MPL-2.0 license file and SPDX headers
- Core config/data model
- Shell command runner skeleton
- Daemon crate skeleton
- CLI crate skeleton
- Headless runtime crate for one-shot and watched shell widgets
- App/GUI crate skeleton
- Optional GUI dependencies so the default workspace stays headless-buildable
- Headless check script and GitHub Actions CI
- Platform backend trait skeleton
- COSMIC-aware backend detection
- Example profile + widget TOML
- Research notes folder
- Pop!_OS/Ubuntu bootstrap helper

Not implemented yet:

- Actual GTK window creation
- Actual layer-shell calls
- X11 window hints
- Log tailing
- Image renderer
- WebKitGTK renderer
- Import/export widget packs

## Repository layout

```text
neodash/
  Cargo.toml
  README.md
  LICENSE
  examples/
    profiles/default.toml
    widgets/date.toml
  crates/
    neodash-core/       shared data model + config parsing
    neodash-exec/       command execution and timeouts
    neodash-tail/       future log tailing crate
    neodash-platform/   Wayland/X11/GNOME/COSMIC backend abstraction
    neodash-renderer/   renderer abstraction
    neodash-daemon/     background service process
    neodash-cli/        command line tool
    neodash-app/        GTK/libadwaita editor app
  docs/
    ROADMAP.md
    NEXT_STEPS.md
    ARCHITECTURE.md
  .github/workflows/
    ci.yml
  research/
    geektool-feature-map.md
    open-source-mining.md
  scripts/
    bootstrap_popos_ubuntu.sh
```

## Build

Install Rust:

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source "$HOME/.cargo/env"
rustup default stable
```

Install Linux desktop build dependencies on Pop!_OS/Ubuntu:

```bash
./scripts/bootstrap_popos_ubuntu.sh
```

From repo root:

```bash
./scripts/check_headless.sh
cargo run -p neodash-cli -- run --command "date" --interval 1000 --watch
cargo run -p neodash-cli -- run-widget examples/widgets/date.toml
cargo run -p neodash-cli -- run-widget examples/widgets/date.toml --once
cargo run -p neodash-cli -- backend
cargo run -p neodash-cli -- example-widget
```

Or run the pieces manually:

```bash
cargo fmt --all -- --check
cargo check --workspace
cargo test --workspace
cargo clippy --workspace -- -D warnings
```

The GUI crate is still a stub. GTK/libadwaita/layer-shell dependencies are optional until the first real graphical window lands. The next implementation commit should create one transparent GTK4 window and then wire layer-shell on supported Wayland compositors.

## Suggested first commit

```bash
git init
git add .
git commit -m "Initial NeoDash MPL-licensed Rust workspace"
```


## User config directory

NeoDash can initialize and use a local config directory:

```bash
cargo run -p neodash-cli -- config-dir
cargo run -p neodash-cli -- config-init --force
cargo run -p neodash-cli -- profile-info default
cargo run -p neodash-cli -- profile-check default
cargo run -p neodash-app --features gui,x11-desktop -- --profile default --debug-frame
```

A bare profile name such as `default` resolves to
`~/.config/neodash/profiles/default.toml`, unless `NEODASH_CONFIG_DIR` points at
another config root. See `docs/CONFIG_DIRECTORY.md`.

## Profile loading

NeoDash can now launch a dashboard from a profile file:

```bash
cargo run -p neodash-app --features gui,x11-desktop -- \
  --profile examples/profiles/default.toml \
  --debug-frame
```

See `docs/PROFILE_LOADING.md` for the current profile format and limitations.

## Profile inspection

Profiles can be inspected without opening the GTK app:

```bash
cargo run -p neodash-cli -- profile-info examples/profiles/default.toml
```

Profile parsing and profile-relative path resolution are shared through
`neodash-core`; see `docs/PROFILE_MODEL.md` for details.


## Profile validation

Validate a profile before launching it:

```bash
cargo run -p neodash-cli -- profile-check examples/profiles/default.toml
```

The GTK app also validates profile launches before opening windows.
