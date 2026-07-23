# NeoDash — COSMIC Independent Widget Surfaces

## Goal

Replace the combined COSMIC diagnostic dashboard with one libcosmic window per
widget while preserving the shared runtime boundary.

## Added

- libcosmic multi-window support in both build modes
- no-main-window daemon startup
- one `WidgetSurface` per `window::Id`
- configured window size
- best-effort configured X11 position
- independent window close lifecycle
- clean exit after the final widget closes
- COSMIC layout/debug modes
- pure surface-plan tests
- architecture guards and documentation

## Important boundary

This phase uses ordinary windows. Native COSMIC layer-shell semantics are the
next phase because desktop layers, anchors, monitor selection, click-through, and
exact Wayland placement require compositor-specific surfaces.

## Suggested commit

```text
feat(cosmic): open independent widget surfaces

- replace the combined COSMIC dashboard with one window per widget
- apply configured size and X11 development-position requests
- add independent widget-window lifecycle handling
- add layout and debug modes for surface development
- prepare native COSMIC layer-surface integration
```
