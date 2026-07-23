# Layout mode

NeoDash has two different preview behaviors:

```text
desktop-widget mode
  undecorated
  non-resizable by default
  may use X11 desktop hints
  intended to behave like pinned widgets

layout mode
  decorated
  resizable
  movable by the window manager
  desktop hints suppressed
  intended for arranging and debugging widgets
```

## Why layout mode exists

Desktop widgets are intentionally hard to treat like normal windows. On X11,
NeoDash may ask the window manager to keep them below normal windows, skip the
taskbar, skip the pager, and appear on all workspaces. The windows are also
undecorated by default.

That is useful for a final dashboard, but bad while tuning positions.

## Use layout mode

```bash
cargo run -p neodash-app --features gui,x11-desktop -- \
  --profile default \
  --layout-mode \
  --debug-frame
```

In layout mode, the window manager should give each widget a normal titlebar and
resize handles. Move or resize the windows, then copy the useful `x`, `y`,
`width`, and `height` values back into the widget TOML files.

NeoDash does not yet save layout changes from dragged windows. That requires the
future editor/control app.

## Disable desktop hints manually

If you do not want the full layout-mode convenience behavior, you can suppress
profile-requested desktop hints directly:

```bash
cargo run -p neodash-app --features gui,x11-desktop -- \
  --profile default \
  --no-desktop-hints \
  --decorated \
  --resizable \
  --debug-frame
```

## Normal desktop-widget launch

```bash
cargo run -p neodash-app --features gui,x11-desktop -- \
  --profile default
```

If the profile sets `desktop_hints = true`, this launches the widgets in
desktop-widget mode.
