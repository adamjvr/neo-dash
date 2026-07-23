# COSMIC widget surfaces

NeoDash's libcosmic host now runs without an extra controller/dashboard window.
It opens one native window for every loaded widget and maps each window ID to one
runtime session.

## Implemented

- one independent libcosmic window per widget
- configured widget width and height
- configured `x/y` requests under the X11 `cosmic-winit` development path
- independent close lifecycle for each widget
- application exit when the final widget closes
- `--layout-mode` header bars and resizing
- `--debug-frame` identity, state, and frame counters
- shared `neodash-runtime` execution and refresh ownership

## Deliberately deferred

Ordinary Wayland toplevel windows cannot provide NeoDash's final desktop-widget
semantics. The following native COSMIC integration phase must implement:

- monitor selection
- anchor-relative placement
- background/bottom/top/overlay layer mapping
- compositor-level click-through input regions
- sticky workspace behavior
- exact COSMIC Wayland positioning

The current phase does not pretend those capabilities are already active.

## Local test

```bash
cargo run -p neodash-cosmic --features cosmic-winit -- \
  --widget examples/widgets/date.toml \
  --widget examples/widgets/uptime.toml \
  --layout-mode \
  --debug-frame
```

Two independent windows should open. Closing one must leave the other running.
Closing the final window must terminate `neodash-cosmic`.
