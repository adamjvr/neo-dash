# Dual frontend development

NeoDash deliberately maintains two native Linux frontend families.

```text
shared NeoDash engine
  neodash-core
  neodash-runtime
  neodash-daemon
  neodash-renderer
  neodash-platform
        |
        +-- GTK4 host
        |     Pop!_OS 22.04
        |     GNOME X11
        |     GNOME Wayland degraded mode
        |     generic layer-shell Wayland
        |
        +-- libcosmic host
              COSMIC on Pop!_OS 24.04 and later
```

COSMIC is not classified as generic Wayland. A COSMIC Wayland session selects
`BackendKind::CosmicNative` and recommends `FrontendKind::Cosmic`.

## Developing while logged into a non-COSMIC desktop

The two libcosmic build modes let both frontends advance from the current
machine:

```bash
# Existing GTK frontend: run and visually test it now.
cargo run -p neodash-app --features gui,x11-desktop -- \
  --profile default \
  --layout-mode \
  --debug-frame

# Native libcosmic UI rendered through winit/X11 for local visual iteration.
cargo run -p neodash-cosmic --features cosmic-winit

# True COSMIC/Wayland build: compile on every phase even outside COSMIC.
cargo check -p neodash-cosmic --features cosmic-wayland
```

Run the complete frontend gate with:

```bash
./scripts/check_frontends.sh
```

## What can be verified outside COSMIC

- shared profile and runtime behavior
- COSMIC application model and message flow
- libcosmic widgets, typography, spacing, and general editor layout
- compilation of the native Wayland target
- GTK/X11 desktop-window behavior
- backend-selection tests

## What still requires a COSMIC login

- compositor-specific desktop/layer placement
- exact multi-monitor anchoring under `cosmic-comp`
- click-through and input-region behavior
- workspace/sticky behavior
- native COSMIC theme/config integration in the actual session
- launch-at-login and session lifecycle integration

Those compositor checks are validation gates, not blockers for ordinary feature
development.

## Development rule

New user-facing functionality should be divided into:

1. toolkit-neutral state and behavior in shared crates;
2. a GTK presentation adapter;
3. a libcosmic presentation adapter;
4. compositor integration behind `neodash-platform` capabilities.

Do not duplicate scheduling, profile parsing, command execution, or persistence in
either frontend.

## Shared runtime parity

Both graphical hosts now consume `neodash-runtime` events:

- GTK drains events on the GLib main loop.
- libcosmic drains events through an iced subscription.
- neither frontend executes shell commands directly.
- each widget keeps its independent runtime-owned refresh interval.

Local COSMIC runtime test:

```bash
cargo run -p neodash-cosmic --features cosmic-winit -- --profile default
```

Native target compile test:

```bash
cargo check -p neodash-cosmic --features cosmic-wayland
```

