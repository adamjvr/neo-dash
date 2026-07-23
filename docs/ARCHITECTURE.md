# NeoDash Architecture

NeoDash is split so the GTK/Wayland/X11 layer never leaks into the data model or command execution code.

```text
neodash-core
  Owns config, IDs, widget model, profile model.

neodash-exec
  Owns shell command execution, timeouts, process isolation rules.

neodash-tail
  Owns file following and log-rotation handling.

neodash-renderer
  Owns render payload abstractions: text, terminal text, image, HTML.

neodash-platform
  Owns backend detection and display-server abstractions.

neodash-daemon
  Runs widgets in the background after the editor closes.

neodash-cli
  Lets users inspect, debug, run, import, export, and switch profiles.

neodash-app
  GTK4/libadwaita visual editor and widget window host.
```

## Purity boundary

The core application is Rust. The desktop integration is native Linux toolkit/protocol binding territory.

```text
Pure Rust-ish:
  config, profiles, command runner, scheduler, transforms, CLI, daemon logic

Rust over native libraries:
  GTK4, libadwaita, Wayland layer-shell, X11 hints, WebKitGTK
```

## First real graphical milestone

1. Create `gtk::Application`.
2. Create one undecorated transparent widget window.
3. Render command output into a label.
4. On COSMIC/wlroots/KDE Wayland, initialize layer-shell.
5. On X11, use normal window hints.
6. Keep GNOME Wayland in degraded mode until a shell-extension bridge exists.


## Build policy

The default workspace must stay buildable without GTK development packages. GUI
dependencies live behind the `neodash-app/gui` feature until the graphical host
code is implemented. This keeps CI fast and protects the Rust-native core from
accidentally turning into a native-library dependency pile.

Use this before committing:

```bash
./scripts/check_headless.sh
```


## Frontend split

`neodash-app` is the GTK compatibility and generic-Linux host.
`neodash-cosmic` is the native libcosmic host.

Both are presentation shells around the same core/runtime/daemon state. COSMIC
Wayland selects `CosmicNative`; it is not routed through the generic layer-shell
classification. The libcosmic host may also run through `cosmic-winit` during
development on a non-COSMIC desktop, but that mode does not claim to validate
COSMIC compositor integration.
